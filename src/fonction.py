"""Wrapper Python pour Terraform CLI — plan, apply, destroy, output."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TerraformResult:
    """Resultat d'une commande Terraform."""
    success: bool
    stdout: str
    stderr: str
    return_code: int


@dataclass
class Terraform:
    """Wrapper leger autour de terraform CLI.

    Usage:
        tf = Terraform(working_dir="./infra", var_file="prod.tfvars")
        tf.init()
        result = tf.plan()
        if result.success:
            tf.apply(auto_approve=True)
    """
    working_dir: str = "."
    var_file: str | None = None
    backend_config: dict[str, str] = field(default_factory=dict)
    env_vars: dict[str, str] = field(default_factory=dict)

    # ── commandes principales ──────────────────────────

    def init(self, reconfigure: bool = False) -> TerraformResult:
        """terraform init avec backend-config optionnel."""
        args = ["init", "-input=false"]
        if reconfigure:
            args.append("-reconfigure")
        for k, v in self.backend_config.items():
            args.append(f"-backend-config={k}={v}")
        return self._run(args)

    def plan(self, out: str | None = None, destroy: bool = False) -> TerraformResult:
        """terraform plan — retourne le diff sans appliquer."""
        args = ["plan", "-input=false"]
        if destroy:
            args.append("-destroy")
        if out:
            args.extend(["-out", out])
        self._append_var_file(args)
        return self._run(args)

    def apply(self, auto_approve: bool = False, plan_file: str | None = None) -> TerraformResult:
        """terraform apply — applique les changements."""
        args = ["apply", "-input=false"]
        if auto_approve:
            args.append("-auto-approve")
        if plan_file:
            args.append(plan_file)
        else:
            self._append_var_file(args)
        return self._run(args)

    def destroy(self, auto_approve: bool = False) -> TerraformResult:
        """terraform destroy — supprime toute l'infra."""
        args = ["destroy", "-input=false"]
        if auto_approve:
            args.append("-auto-approve")
        self._append_var_file(args)
        return self._run(args)

    def output(self, name: str | None = None) -> dict | str:
        """terraform output -json — retourne les outputs parses."""
        args = ["output", "-json"]
        if name:
            args.append(name)
        result = self._run(args)
        if not result.success:
            raise RuntimeError(f"terraform output failed: {result.stderr}")
        return json.loads(result.stdout)

    def validate(self) -> TerraformResult:
        """terraform validate — verifie la syntaxe HCL."""
        return self._run(["validate"])

    def fmt(self, check: bool = False) -> TerraformResult:
        """terraform fmt — formate les fichiers .tf."""
        args = ["fmt"]
        if check:
            args.append("-check")
        return self._run(args)

    # ── internals ──────────────────────────────────────

    def _append_var_file(self, args: list[str]) -> None:
        if self.var_file:
            args.extend(["-var-file", self.var_file])

    def _run(self, args: list[str]) -> TerraformResult:
        """Execute terraform avec les args donnes."""
        cmd = ["terraform", *args]
        env = {**os.environ, **self.env_vars}
        proc = subprocess.run(
            cmd,
            cwd=str(Path(self.working_dir).resolve()),
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        return TerraformResult(
            success=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            return_code=proc.returncode,
        )


if __name__ == "__main__":
    tf = Terraform(working_dir=".", var_file="terraform.tfvars")
    print(tf.validate())
