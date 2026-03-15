"""JARVIS Backup Automation — Système de backup automatisé intelligent.

Backup incrémental, bases SQLite, configs, git bundles avec rotation
et vérification d'intégrité SHA256.

Usage:
    from src.backup_automation import backup_automation
    result = await backup_automation.run_full_backup()
    backups = backup_automation.list_backups()
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.backup_automation")

# ── Chemins par défaut ──────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKUP_ROOT = _PROJECT_ROOT / "backups"
_DATA_DIR = _PROJECT_ROOT / "data"

# Fichiers de config à sauvegarder
_CONFIG_FILES: list[str] = [
    "data/skills.json",
    "data/routines.json",
    "data/voice_aliases.json",
    "data/voice_profiles.json",
]

# Patterns glob pour configs système
_SYSTEM_CONFIG_GLOBS: list[tuple[Path, str]] = [
    (Path.home() / ".config" / "conky", "jarvis*.conf"),
    (Path.home() / ".config" / "systemd" / "user", "jarvis-*.service"),
]


@dataclass
class BackupRecord:
    """Enregistrement d'un backup dans le manifeste."""

    backup_id: str
    backup_type: str          # full, incremental, db, config, bundle
    path: str
    size_bytes: int = 0
    file_count: int = 0
    checksum: str = ""        # SHA256 du manifeste interne
    created_at: float = field(default_factory=time.time)
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)


class BackupAutomation:
    """Système de backup automatisé intelligent pour JARVIS."""

    def __init__(
        self,
        project_root: Path | None = None,
        backup_root: Path | None = None,
    ) -> None:
        self._root = project_root or _PROJECT_ROOT
        self._backup_root = backup_root or _BACKUP_ROOT
        self._data_dir = self._root / "data"
        self._manifest_path = self._backup_root / "manifest.json"
        self._last_backup_path = self._backup_root / ".last_backup_ts"
        self._records: list[BackupRecord] = []

        # Créer les dossiers nécessaires
        for subdir in ("incremental", "databases", "configs", "bundles"):
            (self._backup_root / subdir).mkdir(parents=True, exist_ok=True)

        self._load_manifest()

    # ── Manifest ────────────────────────────────────────────────────

    def _load_manifest(self) -> None:
        """Charge le manifeste des backups existants."""
        if self._manifest_path.exists():
            try:
                data = json.loads(self._manifest_path.read_text())
                self._records = [BackupRecord(**r) for r in data]
            except (json.JSONDecodeError, TypeError):
                logger.warning("Manifeste corrompu, réinitialisé")
                self._records = []

    def _save_manifest(self) -> None:
        """Persiste le manifeste sur disque."""
        from dataclasses import asdict
        payload = [asdict(r) for r in self._records]
        self._manifest_path.write_text(json.dumps(payload, indent=2))

    def _add_record(self, record: BackupRecord) -> None:
        """Ajoute un enregistrement et sauvegarde."""
        self._records.append(record)
        self._save_manifest()

    # ── Utilitaires ─────────────────────────────────────────────────

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Calcule le SHA256 d'un fichier."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _dir_size(path: Path) -> int:
        """Taille totale d'un dossier en octets."""
        total = 0
        if path.is_file():
            return path.stat().st_size
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total

    def _timestamp_tag(self) -> str:
        """Tag horodaté YYYY-MM-DD_HH pour nommage."""
        return datetime.now().strftime("%Y-%m-%d_%H")

    def _get_last_backup_ts(self) -> float:
        """Récupère le timestamp du dernier backup incrémental."""
        if self._last_backup_path.exists():
            try:
                return float(self._last_backup_path.read_text().strip())
            except ValueError:
                pass
        return 0.0

    def _set_last_backup_ts(self) -> None:
        """Enregistre le timestamp courant comme dernier backup."""
        self._last_backup_path.write_text(str(time.time()))

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """Convertit des octets en taille lisible."""
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024  # type: ignore[assignment]
        return f"{size_bytes:.1f} TB"

    # ── Backup incrémental ──────────────────────────────────────────

    def run_incremental(self) -> dict[str, Any]:
        """Backup incrémental : copie uniquement les fichiers modifiés depuis le dernier backup."""
        tag = self._timestamp_tag()
        dest = self._backup_root / "incremental" / tag
        dest.mkdir(parents=True, exist_ok=True)

        last_ts = self._get_last_backup_ts()
        copied: list[str] = []
        errors: list[str] = []
        total_size = 0

        # Parcourir src/ et data/ pour détecter les modifications
        scan_dirs = [self._root / "src", self._data_dir]
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for fpath in scan_dir.rglob("*"):
                if not fpath.is_file():
                    continue
                # Ignorer les .db (gérés séparément) et fichiers trop gros (>100MB)
                if fpath.suffix == ".db" or fpath.stat().st_size > 100 * 1024 * 1024:
                    continue
                try:
                    if fpath.stat().st_mtime > last_ts:
                        rel = fpath.relative_to(self._root)
                        target = dest / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(fpath, target)
                        total_size += fpath.stat().st_size
                        copied.append(str(rel))
                except OSError as exc:
                    errors.append(f"{fpath}: {exc}")

        # Générer checksums
        checksums: dict[str, str] = {}
        for fpath in dest.rglob("*"):
            if fpath.is_file():
                checksums[str(fpath.relative_to(dest))] = self._sha256_file(fpath)

        checksum_path = dest / "checksums.json"
        checksum_path.write_text(json.dumps(checksums, indent=2))

        self._set_last_backup_ts()

        record = BackupRecord(
            backup_id=f"inc-{tag}",
            backup_type="incremental",
            path=str(dest),
            size_bytes=total_size,
            file_count=len(copied),
            checksum=hashlib.sha256(json.dumps(checksums).encode()).hexdigest(),
            metadata={"files": copied[:50], "errors": errors},  # Limiter la taille
        )
        self._add_record(record)

        logger.info(
            "Backup incrémental terminé : %d fichiers, %s",
            len(copied), self._human_size(total_size),
        )
        return {
            "type": "incremental",
            "path": str(dest),
            "files_copied": len(copied),
            "size": self._human_size(total_size),
            "errors": errors,
            "ok": len(errors) == 0,
        }

    # ── Backup bases de données ─────────────────────────────────────

    def run_db_backup(self) -> dict[str, Any]:
        """Backup de toutes les bases SQLite avec vérification d'intégrité."""
        tag = self._timestamp_tag()
        dest = self._backup_root / "databases" / tag
        dest.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, Any]] = []
        total_size = 0
        errors: list[str] = []

        # Trouver toutes les .db dans data/
        db_files = sorted(self._data_dir.glob("*.db"))

        for db_path in db_files:
            backup_path = dest / db_path.name
            try:
                # Utiliser sqlite3 .backup pour une copie cohérente
                src_conn = sqlite3.connect(str(db_path))
                dst_conn = sqlite3.connect(str(backup_path))
                src_conn.backup(dst_conn)
                dst_conn.close()
                src_conn.close()

                # Vérifier l'intégrité du backup
                check_conn = sqlite3.connect(str(backup_path))
                result = check_conn.execute("PRAGMA integrity_check").fetchone()
                check_conn.close()
                integrity_ok = result is not None and result[0] == "ok"

                size = backup_path.stat().st_size
                total_size += size
                checksum = self._sha256_file(backup_path)

                results.append({
                    "db": db_path.name,
                    "size": self._human_size(size),
                    "integrity": integrity_ok,
                    "checksum": checksum,
                })

                if not integrity_ok:
                    errors.append(f"{db_path.name}: integrity check failed")

            except (sqlite3.Error, OSError) as exc:
                errors.append(f"{db_path.name}: {exc}")
                results.append({
                    "db": db_path.name,
                    "error": str(exc),
                    "integrity": False,
                })

        # Rotation : garder les 7 derniers backups DB
        self._rotate_dir(self._backup_root / "databases", keep=7)

        record = BackupRecord(
            backup_id=f"db-{tag}",
            backup_type="db",
            path=str(dest),
            size_bytes=total_size,
            file_count=len(db_files),
            metadata={"databases": [r["db"] for r in results], "errors": errors},
        )
        self._add_record(record)

        logger.info(
            "Backup DB terminé : %d bases, %s",
            len(db_files), self._human_size(total_size),
        )
        return {
            "type": "db",
            "path": str(dest),
            "databases": results,
            "total_size": self._human_size(total_size),
            "errors": errors,
            "ok": len(errors) == 0,
        }

    # ── Backup configs ──────────────────────────────────────────────

    def _run_config_backup(self) -> dict[str, Any]:
        """Backup des fichiers de configuration JARVIS."""
        tag = self._timestamp_tag()
        dest = self._backup_root / "configs" / tag
        dest.mkdir(parents=True, exist_ok=True)

        copied: list[str] = []
        errors: list[str] = []
        total_size = 0

        # Fichiers de config dans le projet
        for rel_path in _CONFIG_FILES:
            src = self._root / rel_path
            if src.exists():
                try:
                    target = dest / rel_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, target)
                    total_size += src.stat().st_size
                    copied.append(rel_path)
                except OSError as exc:
                    errors.append(f"{rel_path}: {exc}")

        # Configs système (conky, systemd)
        for base_dir, pattern in _SYSTEM_CONFIG_GLOBS:
            if base_dir.exists():
                for fpath in base_dir.glob(pattern):
                    if fpath.is_file():
                        try:
                            rel = f"system/{base_dir.name}/{fpath.name}"
                            target = dest / rel
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(fpath, target)
                            total_size += fpath.stat().st_size
                            copied.append(rel)
                        except OSError as exc:
                            errors.append(f"{fpath}: {exc}")

        record = BackupRecord(
            backup_id=f"cfg-{tag}",
            backup_type="config",
            path=str(dest),
            size_bytes=total_size,
            file_count=len(copied),
            metadata={"files": copied, "errors": errors},
        )
        self._add_record(record)

        return {
            "type": "config",
            "path": str(dest),
            "files_copied": len(copied),
            "size": self._human_size(total_size),
            "errors": errors,
            "ok": len(errors) == 0,
        }

    # ── Git bundle ──────────────────────────────────────────────────

    def _run_git_bundle(self) -> dict[str, Any]:
        """Crée un git bundle contenant tous les commits."""
        tag = self._timestamp_tag()
        bundle_dir = self._backup_root / "bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundle_dir / f"jarvis-{tag}.bundle"

        # Vérifier si on est dans un repo git
        git_dir = self._root / ".git"
        if not git_dir.exists():
            return {
                "type": "bundle",
                "ok": False,
                "error": "Pas de dépôt git détecté",
            }

        try:
            result = subprocess.run(
                ["git", "bundle", "create", str(bundle_path), "--all"],
                cwd=str(self._root),
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                return {
                    "type": "bundle",
                    "ok": False,
                    "error": result.stderr.strip(),
                }

            size = bundle_path.stat().st_size
            checksum = self._sha256_file(bundle_path)

            # Vérifier le bundle
            verify = subprocess.run(
                ["git", "bundle", "verify", str(bundle_path)],
                cwd=str(self._root),
                capture_output=True,
                text=True,
                timeout=60,
            )

            record = BackupRecord(
                backup_id=f"bundle-{tag}",
                backup_type="bundle",
                path=str(bundle_path),
                size_bytes=size,
                file_count=1,
                checksum=checksum,
                metadata={"verified": verify.returncode == 0},
            )
            self._add_record(record)

            return {
                "type": "bundle",
                "path": str(bundle_path),
                "size": self._human_size(size),
                "checksum": checksum,
                "verified": verify.returncode == 0,
                "ok": True,
            }

        except (subprocess.TimeoutExpired, OSError) as exc:
            return {"type": "bundle", "ok": False, "error": str(exc)}

    # ── Backup complet ──────────────────────────────────────────────

    def run_full_backup(self) -> dict[str, Any]:
        """Lance un backup complet : incrémental + DB + configs + bundle."""
        started = time.time()
        logger.info("Démarrage backup complet JARVIS")

        results: dict[str, Any] = {
            "started_at": datetime.now().isoformat(),
            "incremental": self.run_incremental(),
            "databases": self.run_db_backup(),
            "configs": self._run_config_backup(),
            "bundle": self._run_git_bundle(),
        }

        elapsed = time.time() - started
        results["elapsed_seconds"] = round(elapsed, 1)
        results["total_size"] = self._human_size(self._total_backup_size())

        # Appliquer la rotation
        self.cleanup_old_backups()

        all_ok = all(
            results[k].get("ok", False)
            for k in ("incremental", "databases", "configs", "bundle")
        )
        results["ok"] = all_ok

        logger.info(
            "Backup complet terminé en %.1fs — taille totale : %s",
            elapsed, results["total_size"],
        )
        return results

    # ── Vérification ────────────────────────────────────────────────

    def verify_backup(self, path: str | Path) -> bool:
        """Vérifie l'intégrité d'un backup via checksums SHA256."""
        backup_path = Path(path)

        if not backup_path.exists():
            logger.error("Backup introuvable : %s", path)
            return False

        # Si c'est un fichier unique (.db, .bundle)
        if backup_path.is_file():
            # Vérifier si c'est une base SQLite
            if backup_path.suffix == ".db":
                try:
                    conn = sqlite3.connect(str(backup_path))
                    result = conn.execute("PRAGMA integrity_check").fetchone()
                    conn.close()
                    ok = result is not None and result[0] == "ok"
                    logger.info("Vérification DB %s : %s", backup_path.name, "OK" if ok else "ÉCHEC")
                    return ok
                except sqlite3.Error as exc:
                    logger.error("Erreur vérification DB %s : %s", backup_path.name, exc)
                    return False

            # Vérifier si c'est un bundle git
            if backup_path.suffix == ".bundle":
                try:
                    result = subprocess.run(
                        ["git", "bundle", "verify", str(backup_path)],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    ok = result.returncode == 0
                    logger.info("Vérification bundle %s : %s", backup_path.name, "OK" if ok else "ÉCHEC")
                    return ok
                except (subprocess.TimeoutExpired, OSError):
                    return False

            # Fichier ordinaire — vérifier qu'il est lisible
            return backup_path.stat().st_size > 0

        # Si c'est un dossier, vérifier les checksums
        checksum_file = backup_path / "checksums.json"
        if checksum_file.exists():
            try:
                checksums = json.loads(checksum_file.read_text())
                mismatches: list[str] = []
                for rel_path, expected_hash in checksums.items():
                    fpath = backup_path / rel_path
                    if not fpath.exists():
                        mismatches.append(f"Manquant: {rel_path}")
                        continue
                    actual = self._sha256_file(fpath)
                    if actual != expected_hash:
                        mismatches.append(f"Checksum différent: {rel_path}")

                if mismatches:
                    logger.warning("Vérification backup %s : %d problèmes", path, len(mismatches))
                    return False

                logger.info("Vérification backup %s : OK (%d fichiers)", path, len(checksums))
                return True

            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Erreur lecture checksums : %s", exc)
                return False

        # Pas de checksums — vérifier que le dossier n'est pas vide
        files = list(backup_path.rglob("*"))
        has_files = any(f.is_file() for f in files)
        logger.info("Vérification backup %s : %s (pas de checksums)", path, "OK" if has_files else "VIDE")
        return has_files

    # ── Liste des backups ───────────────────────────────────────────

    def list_backups(self) -> list[dict[str, Any]]:
        """Liste tous les backups avec taille et date."""
        result: list[dict[str, Any]] = []
        for record in sorted(self._records, key=lambda r: r.created_at, reverse=True):
            p = Path(record.path)
            exists = p.exists()
            actual_size = self._dir_size(p) if exists else 0

            result.append({
                "id": record.backup_id,
                "type": record.backup_type,
                "path": record.path,
                "size": self._human_size(actual_size),
                "size_bytes": actual_size,
                "file_count": record.file_count,
                "created_at": datetime.fromtimestamp(record.created_at).isoformat(),
                "status": record.status,
                "exists": exists,
            })
        return result

    # ── Restauration DB ─────────────────────────────────────────────

    def restore_db(self, backup_path: str | Path, target_db: str | Path) -> dict[str, Any]:
        """Restaure une base SQLite depuis un backup."""
        src = Path(backup_path)
        dst = Path(target_db)

        if not src.exists():
            return {"ok": False, "error": f"Backup introuvable : {src}"}

        if not src.suffix == ".db":
            return {"ok": False, "error": "Le backup doit être un fichier .db"}

        # Vérifier l'intégrité du backup avant restauration
        if not self.verify_backup(src):
            return {"ok": False, "error": "Backup corrompu (integrity check échoué)"}

        try:
            # Sauvegarder la base actuelle avant écrasement
            if dst.exists():
                safety_backup = dst.with_suffix(".db.pre_restore")
                shutil.copy2(dst, safety_backup)
                logger.info("Sauvegarde de sécurité : %s", safety_backup)

            # Restaurer via sqlite3 backup API
            src_conn = sqlite3.connect(str(src))
            dst_conn = sqlite3.connect(str(dst))
            src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            # Vérifier la base restaurée
            check_conn = sqlite3.connect(str(dst))
            result = check_conn.execute("PRAGMA integrity_check").fetchone()
            check_conn.close()
            integrity_ok = result is not None and result[0] == "ok"

            logger.info(
                "Restauration %s → %s : %s",
                src.name, dst, "OK" if integrity_ok else "ÉCHEC intégrité",
            )
            return {
                "ok": integrity_ok,
                "source": str(src),
                "target": str(dst),
                "size": self._human_size(dst.stat().st_size),
            }

        except (sqlite3.Error, OSError) as exc:
            logger.error("Erreur restauration : %s", exc)
            return {"ok": False, "error": str(exc)}

    # ── Rotation ────────────────────────────────────────────────────

    def _rotate_dir(self, parent: Path, keep: int = 7) -> list[str]:
        """Rotation simple : garde les N dossiers les plus récents."""
        if not parent.exists():
            return []

        subdirs = sorted(
            [d for d in parent.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

        removed: list[str] = []
        for old_dir in subdirs[keep:]:
            try:
                shutil.rmtree(old_dir)
                removed.append(old_dir.name)
                logger.info("Rotation : supprimé %s", old_dir)
            except OSError as exc:
                logger.warning("Impossible de supprimer %s : %s", old_dir, exc)

        return removed

    def cleanup_old_backups(self) -> dict[str, Any]:
        """Applique la politique de rotation complète.

        - Quotidien (incremental) : garde 7 jours
        - Hebdomadaire (databases) : garde 4 semaines
        - Mensuel (bundles) : garde 6 mois
        """
        now = time.time()
        removed: dict[str, list[str]] = {
            "incremental": [],
            "databases": [],
            "bundles": [],
            "configs": [],
        }

        # Incrémental : garder 7 jours
        removed["incremental"] = self._rotate_dir(
            self._backup_root / "incremental", keep=7
        )

        # Databases : garder 4 semaines (28 backups si quotidien)
        removed["databases"] = self._rotate_dir(
            self._backup_root / "databases", keep=28
        )

        # Configs : garder 4 semaines
        removed["configs"] = self._rotate_dir(
            self._backup_root / "configs", keep=28
        )

        # Bundles : garder 6 mois (~180 si quotidien, mais on limite à 26 = bi-hebdo)
        bundle_dir = self._backup_root / "bundles"
        if bundle_dir.exists():
            bundles = sorted(
                [f for f in bundle_dir.iterdir() if f.is_file() and f.suffix == ".bundle"],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            for old_bundle in bundles[26:]:
                try:
                    old_bundle.unlink()
                    removed["bundles"].append(old_bundle.name)
                    logger.info("Rotation bundle : supprimé %s", old_bundle.name)
                except OSError as exc:
                    logger.warning("Impossible de supprimer bundle %s : %s", old_bundle, exc)

        # Nettoyer le manifeste : retirer les entrées dont le path n'existe plus
        self._records = [
            r for r in self._records if Path(r.path).exists()
        ]
        self._save_manifest()

        total_removed = sum(len(v) for v in removed.values())
        logger.info("Rotation terminée : %d éléments supprimés", total_removed)
        return {
            "removed": removed,
            "total_removed": total_removed,
            "remaining_backups": len(self._records),
        }

    # ── Taille totale ───────────────────────────────────────────────

    def _total_backup_size(self) -> int:
        """Calcule la taille totale de tous les backups."""
        total = 0
        for subdir in ("incremental", "databases", "configs", "bundles"):
            path = self._backup_root / subdir
            if path.exists():
                total += self._dir_size(path)
        return total

    # ── Status rapide ───────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Retourne un résumé de l'état des backups."""
        last_ts = self._get_last_backup_ts()
        last_dt = datetime.fromtimestamp(last_ts).isoformat() if last_ts > 0 else "jamais"

        return {
            "total_backups": len(self._records),
            "total_size": self._human_size(self._total_backup_size()),
            "last_backup": last_dt,
            "backup_root": str(self._backup_root),
            "types": {
                btype: len([r for r in self._records if r.backup_type == btype])
                for btype in ("incremental", "db", "config", "bundle")
            },
        }


# ── Singleton ───────────────────────────────────────────────────────
backup_automation = BackupAutomation()


# ── Point d'entrée CLI ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "full"

    ba = backup_automation

    if cmd == "full":
        result = ba.run_full_backup()
    elif cmd == "incremental":
        result = ba.run_incremental()
    elif cmd == "db":
        result = ba.run_db_backup()
    elif cmd == "list":
        result = ba.list_backups()
    elif cmd == "status":
        result = ba.status()
    elif cmd == "cleanup":
        result = ba.cleanup_old_backups()
    elif cmd == "verify" and len(sys.argv) > 2:
        ok = ba.verify_backup(sys.argv[2])
        result = {"path": sys.argv[2], "ok": ok}
    else:
        print("Usage: backup_automation.py [full|incremental|db|list|status|cleanup|verify <path>]")
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))
