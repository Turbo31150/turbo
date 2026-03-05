"""
OS PILOT v3.0 - Controle Neural Total
Controle physique: fenetres, clavier, souris, apps, fichiers, navigateur, systeme
Securite: pyautogui.FAILSAFE = True (coin ecran = stop)
FIX: pyperclip pour texte unicode/accents (pyautogui.write ne gere pas)
"""
import pyautogui
import time
import subprocess
import os
import sys
import webbrowser

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    import pyperclip
    PYPERCLIP_OK = True
except ImportError:
    PYPERCLIP_OK = False

# SECURITE : Deplacer la souris dans un coin stoppe tout
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1  # delai entre actions

LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')

# SPECIAL_FOLDERS - Mapping noms francais vers paths Windows
SPECIAL_FOLDERS = {
    "bureau": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\franc"), "Desktop"),
    "documents": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\franc"), "Documents"),
    "telechargements": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\franc"), "Downloads"),
    "downloads": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\franc"), "Downloads"),
    "images": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\franc"), "Pictures"),
    "musique": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\franc"), "Music"),
    "videos": os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\franc"), "Videos"),
    "disque c": "C:\\",
    "disque d": "D:\\",
    "disque f": "F:\\",
    "f bureau": r"F:\BUREAU",
    "production": r"F:\BUREAU\TRADING_V2_PRODUCTION",
    "trading": r"F:\BUREAU\TRADING_V2_PRODUCTION",
    "scripts": r"F:\BUREAU\TRADING_V2_PRODUCTION\scripts",
    "logs": r"F:\BUREAU\TRADING_V2_PRODUCTION\logs",
    "config": r"F:\BUREAU\TRADING_V2_PRODUCTION\config",
    "database": r"F:\BUREAU\TRADING_V2_PRODUCTION\database",
}


def _type_unicode(text):
    """Tape du texte avec support accents/unicode via clipboard"""
    if PYPERCLIP_OK:
        old = pyperclip.paste()
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyperclip.copy(old)  # restaure le clipboard
    else:
        # Fallback ASCII only
        pyautogui.write(text, interval=0.01)


def get_system_info():
    """Retourne un dict avec CPU, RAM, disques"""
    if not PSUTIL_OK:
        return {"error": "psutil non installe"}
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disks = {}
    for part in psutil.disk_partitions():
        if 'fixed' in part.opts or part.fstype:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks[part.mountpoint] = {
                    "free_gb": round(usage.free / 1e9, 1),
                    "total_gb": round(usage.total / 1e9, 1),
                    "pct": usage.percent
                }
            except PermissionError:
                pass
    return {
        "cpu_pct": cpu,
        "ram_used_gb": round(mem.used / 1e9, 1),
        "ram_total_gb": round(mem.total / 1e9, 1),
        "ram_pct": mem.percent,
        "disks": disks,
    }


def get_running_apps():
    """Liste les fenetres visibles"""
    if not PSUTIL_OK:
        return []
    apps = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            info = proc.info
            mem_mb = info['memory_info'].rss / 1e6 if info['memory_info'] else 0
            if mem_mb > 50:  # only significant processes
                apps.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "mem_mb": round(mem_mb, 0)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    apps.sort(key=lambda x: x['mem_mb'], reverse=True)
    return apps[:15]


def run_command(intent, params=None):
    """Execute l'action physique demandee par le Cerveau"""
    print(f"  PILOT ACTION: {intent} [{params}]")

    try:
        # === APPLICATIONS ===
        if intent == "OPEN_APP":
            pyautogui.press('win')
            time.sleep(0.3)
            _type_unicode(params or '')
            time.sleep(0.5)
            pyautogui.press('enter')

        elif intent == "OPEN_URL":
            webbrowser.open(params or 'https://www.google.com')

        elif intent == "OPEN_FOLDER":
            path = params or 'C:\\'
            # Lookup SPECIAL_FOLDERS
            path_lower = path.lower().strip()
            if path_lower in SPECIAL_FOLDERS:
                path = SPECIAL_FOLDERS[path_lower]
            if os.path.exists(path):
                os.startfile(path)
            else:
                # Fallback: Win+R run dialog
                pyautogui.hotkey('win', 'r')
                time.sleep(0.3)
                _type_unicode(path)
                time.sleep(0.1)
                pyautogui.press('enter')

        elif intent == "CLOSE_WINDOW":
            pyautogui.hotkey('alt', 'f4')

        elif intent == "KILL_PROCESS":
            if params:
                os.system(f'taskkill /f /im {params}')
                return f"Process {params} tue"

        # === FENETRES ===
        elif intent == "SNAP_LEFT":
            pyautogui.hotkey('win', 'left')

        elif intent == "SNAP_RIGHT":
            pyautogui.hotkey('win', 'right')

        elif intent == "MAXIMIZE":
            pyautogui.hotkey('win', 'up')

        elif intent == "MINIMIZE":
            pyautogui.hotkey('win', 'down')

        elif intent == "MINIMIZE_ALL":
            pyautogui.hotkey('win', 'm')

        elif intent == "SWITCH_WINDOW":
            pyautogui.hotkey('alt', 'tab')

        elif intent == "TASK_MANAGER":
            pyautogui.hotkey('ctrl', 'shift', 'esc')

        elif intent == "DESKTOP":
            pyautogui.hotkey('win', 'd')

        # === NAVIGATEUR ===
        elif intent == "NEW_TAB":
            pyautogui.hotkey('ctrl', 't')

        elif intent == "CLOSE_TAB":
            pyautogui.hotkey('ctrl', 'w')

        elif intent == "NEXT_TAB":
            pyautogui.hotkey('ctrl', 'tab')

        elif intent == "PREV_TAB":
            pyautogui.hotkey('ctrl', 'shift', 'tab')

        elif intent == "REFRESH":
            pyautogui.press('f5')

        elif intent == "BACK":
            pyautogui.hotkey('alt', 'left')

        elif intent == "FORWARD":
            pyautogui.hotkey('alt', 'right')

        elif intent == "ADDRESS_BAR":
            pyautogui.hotkey('ctrl', 'l')

        elif intent == "GO_TO_URL":
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.2)
            _type_unicode(params or '')
            time.sleep(0.1)
            pyautogui.press('enter')

        # === NAVIGATION & SAISIE ===
        elif intent == "SCROLL_DOWN":
            amount = int(params) if params and params.isdigit() else 500
            pyautogui.scroll(-amount)

        elif intent == "SCROLL_UP":
            amount = int(params) if params and params.isdigit() else 500
            pyautogui.scroll(amount)

        elif intent == "TYPE_TEXT":
            if params:
                _type_unicode(params)

        elif intent == "PRESS_KEY":
            if params:
                key = params.lower().strip()
                pyautogui.press(key)

        elif intent == "PRESS_ENTER":
            pyautogui.press('enter')

        elif intent == "PRESS_ESC":
            pyautogui.press('escape')

        elif intent == "PRESS_TAB":
            pyautogui.press('tab')

        elif intent == "PRESS_BACKSPACE":
            pyautogui.press('backspace')

        # === SOURIS ===
        elif intent == "CLICK":
            pyautogui.click()

        elif intent == "DOUBLE_CLICK":
            pyautogui.doubleClick()

        elif intent == "RIGHT_CLICK":
            pyautogui.rightClick()

        elif intent == "CLICK_AT":
            if params:
                parts = str(params).replace(',', ' ').split()
                if len(parts) >= 2:
                    x, y = int(parts[0]), int(parts[1])
                    pyautogui.click(x, y)

        elif intent == "MOVE_MOUSE":
            if params:
                parts = str(params).replace(',', ' ').split()
                if len(parts) >= 2:
                    x, y = int(parts[0]), int(parts[1])
                    pyautogui.moveTo(x, y, duration=0.3)

        # === RACCOURCIS CLAVIER ===
        elif intent == "HOTKEY":
            if params:
                keys = [k.strip() for k in params.split('+')]
                pyautogui.hotkey(*keys)

        elif intent == "COPY":
            pyautogui.hotkey('ctrl', 'c')

        elif intent == "PASTE":
            pyautogui.hotkey('ctrl', 'v')

        elif intent == "CUT":
            pyautogui.hotkey('ctrl', 'x')

        elif intent == "UNDO":
            pyautogui.hotkey('ctrl', 'z')

        elif intent == "REDO":
            pyautogui.hotkey('ctrl', 'y')

        elif intent == "SAVE":
            pyautogui.hotkey('ctrl', 's')

        elif intent == "SELECT_ALL":
            pyautogui.hotkey('ctrl', 'a')

        elif intent == "FIND":
            pyautogui.hotkey('ctrl', 'f')

        elif intent == "NEW_WINDOW":
            pyautogui.hotkey('ctrl', 'n')

        elif intent == "READ_CLIPBOARD":
            if PYPERCLIP_OK:
                content = pyperclip.paste()
                print(f"  CLIPBOARD: {content[:200]}")
                return content
            return "pyperclip non installe"

        # === VOLUME ===
        elif intent == "VOLUME_UP":
            pyautogui.press('volumeup', presses=5)

        elif intent == "VOLUME_DOWN":
            pyautogui.press('volumedown', presses=5)

        elif intent == "VOLUME_MUTE":
            pyautogui.press('volumemute')

        # === SYSTEME ===
        elif intent == "SCREENSHOT":
            os.makedirs(LOGS_DIR, exist_ok=True)
            img = pyautogui.screenshot()
            path = os.path.join(LOGS_DIR, f'screen_{int(time.time())}.png')
            img.save(path)
            print(f"  Screenshot: {path}")
            return path

        elif intent == "CHECK_SYSTEM":
            info = get_system_info()
            if 'error' in info:
                print(f"  SYSTEM: {info['error']}")
            else:
                disks_str = ", ".join(f"{k}: {v['free_gb']}GB libre" for k, v in info.get('disks', {}).items())
                print(f"  SYSTEM: CPU={info['cpu_pct']}% RAM={info['ram_pct']}% | {disks_str}")
            return info

        elif intent == "LIST_APPS":
            apps = get_running_apps()
            for a in apps[:10]:
                print(f"  APP: {a['name']} (PID {a['pid']}, {a['mem_mb']}MB)")
            return apps

        elif intent == "RUN_CMD":
            if params:
                result = subprocess.run(params, shell=True, capture_output=True, text=True, timeout=10)
                output = result.stdout[:500] or result.stderr[:500]
                print(f"  CMD: {output[:200]}")
                return output

        elif intent == "LOCK_PC":
            os.system('rundll32.exe user32.dll,LockWorkStation')

        elif intent == "SLEEP_PC":
            os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')

        # === SYSTEME ETENDU ===
        elif intent == "SETTINGS":
            pyautogui.hotkey('win', 'i')

        elif intent == "NOTIFICATIONS":
            pyautogui.hotkey('win', 'n')

        elif intent == "VIRTUAL_DESKTOPS":
            pyautogui.hotkey('win', 'tab')

        elif intent == "NEW_DESKTOP":
            pyautogui.hotkey('win', 'ctrl', 'd')

        elif intent == "SEARCH_FILES":
            pyautogui.hotkey('win', 's')

        elif intent == "SEARCH_WEB":
            if params:
                url = f"https://www.google.com/search?q={params.replace(' ', '+')}"
                webbrowser.open(url)
            else:
                webbrowser.open("https://www.google.com")

        # === FICHIERS / DOSSIERS ===
        elif intent == "NEW_FOLDER":
            pyautogui.hotkey('ctrl', 'shift', 'n')

        elif intent == "RENAME_FILE":
            pyautogui.press('f2')

        elif intent == "DELETE_FILE":
            pyautogui.press('delete')

        elif intent == "FILE_PROPERTIES":
            pyautogui.hotkey('alt', 'enter')

        else:
            print(f"  Action inconnue: {intent}")
            return f"UNKNOWN_ACTION: {intent}"

        return "OK"

    except Exception as e:
        print(f"  Erreur Pilot: {e}")
        return f"ERROR: {e}"


if __name__ == "__main__":
    print("Test OS Pilot v3.0...")
    info = run_command("CHECK_SYSTEM")
    if info and isinstance(info, dict) and 'error' not in info:
        print(f"  CPU={info.get('cpu_pct')}% RAM={info.get('ram_pct')}%")
        for disk, dinfo in info.get('disks', {}).items():
            print(f"  {disk}: {dinfo['free_gb']}GB libre / {dinfo['total_gb']}GB")
    apps = run_command("LIST_APPS")
    if apps:
        print(f"  Top apps: {', '.join(a['name'] for a in apps[:5])}")
    print("OK - Pilot v3.0 operationnel")
