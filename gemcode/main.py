# gemcode/main.py
# GemCode v0.7 Production Build
# AI + Tools + Sessions + Auto Repo Context + Patch Mode

import os
import json
import subprocess
from pathlib import Path
import typer
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

app = typer.Typer(help="GemCode CLI")

# =====================================================
# PATHS
# =====================================================

HOME = Path.home()
BASE = HOME / ".gemcode"
SESSIONS = BASE / "sessions"
CFG = BASE / "config.json"

BASE.mkdir(exist_ok=True)
SESSIONS.mkdir(exist_ok=True)

if not CFG.exists():
    CFG.write_text(json.dumps({
        "model": "gemma4:latest"
    }, indent=2))

# =====================================================
# CONFIG
# =====================================================

def load_cfg():
    try:
        return json.loads(CFG.read_text())
    except:
        return {"model": "gemma4:latest"}

def save_cfg(cfg):
    CFG.write_text(json.dumps(cfg, indent=2))

# =====================================================
# STATE
# =====================================================

def new_state():
    cfg = load_cfg()
    return {
        "model": cfg.get("model", "gemma4:latest"),
        "messages": [],
        "mode": "plan"
    }

# =====================================================
# SESSIONS
# =====================================================

def next_session_id():
    ids = []
    for f in SESSIONS.glob("*.json"):
        try:
            ids.append(int(f.stem))
        except:
            pass
    return max(ids, default=0) + 1

def save_session(sid, state):
    try:
        (SESSIONS / f"{sid}.json").write_text(json.dumps(state, indent=2))
    except:
        pass

def load_session(sid):
    path = SESSIONS / f"{sid}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except:
        return new_state()

# =====================================================
# FILE OPS
# =====================================================

def read_file(name):
    p = Path(name)
    if not p.exists():
        return None
    try:
        return p.read_text()
    except:
        return None

def write_file(name, content):
    Path(name).write_text(content)

# =====================================================
# REPO CONTEXT
# =====================================================

def gather_repo_context():
    ctx = []

    if Path("README.md").exists():
        txt = read_file("README.md")
        if txt:
            ctx.append("README.md:\n" + txt[:3000])

    pyfiles = list(Path(".").glob("*.py"))[:5]

    for f in pyfiles:
        txt = read_file(str(f))
        if txt:
            ctx.append(f"{f.name}:\n{txt[:2000]}")

    return "\n\n".join(ctx)

# =====================================================
# MODEL
# =====================================================

def ask_model(prompt, model, state):
    history = ""

    for m in state["messages"][-6:]:
        history += f"{m['role']}: {m['content']}\n"

    repo = gather_repo_context()

    final_prompt = f"""
You are GemCode AI, a coding CLI assistant.

Project context:
{repo}

Conversation:
{history}

User:
{prompt}

Answer clearly and helpfully.
"""

    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=final_prompt,
            text=True,
            capture_output=True
        )

        out = result.stdout.strip()

        if not out:
            return "(No response from model)"

        return out

    except Exception as e:
        return f"Model error: {e}"

# =====================================================
# CREATE TOOLS
# =====================================================

def create_tools(prompt):
    low = prompt.lower()

    if "create hello.py" in low:
        write_file("hello.py", "print('hello world')\n")
        print("[green]Created hello.py[/green]")
        return True

    if "create app.py" in low:
        code = """from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Hello World'

if __name__ == '__main__':
    app.run(debug=True)
"""
        write_file("app.py", code)
        print("[green]Created app.py[/green]")
        return True

    return False

# =====================================================
# EDIT TOOLS
# =====================================================

def edit_tools(prompt, state):
    low = prompt.lower()

    if "edit hello.py" in low and "goodbye" in low:
        old = read_file("hello.py")

        if old is None:
            print("[red]hello.py not found[/red]")
            return True

        new = old.rstrip() + "\nprint('goodbye world')\n"

        print(Panel(
f"""--- hello.py
+++ hello.py
@@
{old.rstrip()}
+print('goodbye world')
""", title="Patch Preview"))

        if state["mode"] == "plan":
            if not Confirm.ask("Apply patch?"):
                print("Cancelled.")
                return True

        write_file("hello.py", new)
        print("[green]Edited hello.py[/green]")
        return True

    return False

# =====================================================
# COMMANDS
# =====================================================

def slash(cmd, state):
    parts = cmd.split()

    if cmd == "/help":
        print("""
/help
/exit
/pwd
/ls
/tree
/read FILE
/model NAME
/mode plan|auto
/status
/compact

Shell:
!ls
!python app.py
""")
        return

    if cmd == "/exit":
        raise EOFError

    if cmd == "/pwd":
        print(os.getcwd())
        return

    if cmd == "/ls":
        for x in os.listdir("."):
            print(x)
        return

    if cmd == "/tree":
        for root, dirs, files in os.walk("."):
            level = root.replace(os.getcwd(), "").count(os.sep)
            indent = " " * (level * 2)
            print(f"{indent}{os.path.basename(root)}/")
            for f in files:
                print(f"{indent}  {f}")
        return

    if parts[0] == "/read" and len(parts) > 1:
        txt = read_file(parts[1])
        print(txt if txt else "File not found.")
        return

    if parts[0] == "/model" and len(parts) > 1:
        state["model"] = parts[1]
        cfg = load_cfg()
        cfg["model"] = parts[1]
        save_cfg(cfg)
        print(f"Model changed to {parts[1]}")
        return

    if parts[0] == "/mode" and len(parts) > 1:
        if parts[1] in ["plan", "auto"]:
            state["mode"] = parts[1]
            print(f"Mode changed to {parts[1]}")
        return

    if cmd == "/status":
        print(f"Model: {state['model']}")
        print(f"Mode : {state['mode']}")
        return

    if cmd == "/compact":
        state["messages"] = state["messages"][-4:]
        print("Conversation compacted.")
        return

# =====================================================
# LOOP
# =====================================================

def run_chat(sid, state):
    print(Panel(f"GemCode | Session #{sid}"))

    while True:
        try:
            prompt = Prompt.ask(">")

            if not prompt.strip():
                continue

            if prompt.startswith("/"):
                slash(prompt, state)
                save_session(sid, state)
                continue

            if prompt.startswith("!"):
                subprocess.run(prompt[1:], shell=True)
                continue

            if create_tools(prompt):
                save_session(sid, state)
                continue

            if edit_tools(prompt, state):
                save_session(sid, state)
                continue

            print("Thinking...")

            reply = ask_model(prompt, state["model"], state)

            print(reply)

            state["messages"].append({
                "role": "user",
                "content": prompt
            })

            state["messages"].append({
                "role": "assistant",
                "content": reply
            })

            save_session(sid, state)

        except KeyboardInterrupt:
            print("\nCancelled")

        except EOFError:
            save_session(sid, state)
            print("Bye.")
            return

        except Exception as e:
            print(f"[red]Error:[/red] {e}")

# =====================================================
# CLI
# =====================================================

@app.command()
def chat():
    sid = next_session_id()
    state = new_state()
    save_session(sid, state)
    run_chat(sid, state)

@app.command()
def resume(id: int = None):
    if id is None:
        ids = []

        for f in SESSIONS.glob("*.json"):
            try:
                ids.append(int(f.stem))
            except:
                pass

        if not ids:
            print("No sessions found.")
            return

        id = max(ids)

    state = load_session(id)

    if not state:
        print("Session not found.")
        return

    run_chat(id, state)

@app.command()
def sessions():
    for f in sorted(SESSIONS.glob("*.json"), key=lambda x: int(x.stem)):
        print(f.stem)

if __name__ == "__main__":
    app()
