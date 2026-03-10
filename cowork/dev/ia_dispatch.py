#!/usr/bin/env python3
"""IA Dispatch — send a prompt to a specific cluster node."""
import argparse, json, urllib.request

NODES = {
    "m1": {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b", "type": "lmstudio"},
    "ol1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b", "type": "ollama"},
    "m2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio"},
    "m3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b", "type": "lmstudio"},
}

def dispatch(node: str, prompt: str) -> str:
    cfg = NODES.get(node)
    if not cfg:
        return f"Unknown node: {node}. Available: {', '.join(NODES)}"

    if cfg["type"] == "ollama":
        payload = json.dumps({
            "model": cfg["model"],
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }).encode()
    else:
        input_text = f"/nothink\n{prompt}" if "deepseek" not in cfg["model"] else prompt
        payload = json.dumps({
            "model": cfg["model"],
            "input": input_text,
            "temperature": 0.2,
            "max_output_tokens": 1024,
            "stream": False,
            "store": False,
        }).encode()

    req = urllib.request.Request(
        cfg["url"], data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        if cfg["type"] == "ollama":
            return data.get("message", {}).get("content", "No response")
        else:
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c.get("text", "No response")
            return "No response"
    except Exception as e:
        return f"Error: {e}"

def main():
    parser = argparse.ArgumentParser(description="Dispatch prompt to cluster node")
    parser.add_argument("prompt", help="Prompt to send")
    parser.add_argument("--node", "-n", default="m1", choices=list(NODES.keys()))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    print(f"[{args.node.upper()}] ", end="", flush=True)
    result = dispatch(args.node, args.prompt)
    print(result)

if __name__ == "__main__":
    main()
