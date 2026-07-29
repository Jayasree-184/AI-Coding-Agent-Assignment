"""
A small AI coding agent.

Usage:
    export GROQ_API_KEY=gsk_...
    python agent.py <path-to-target-repo> "<one-line product request>"

The agent explores the target repo with read-only tools, decides on an
implementation plan, edits files with write_file, then calls `finish`
with the plan and a summary. Every tool call is printed as it happens
so the run is fully auditable (and demoable on screen recording).
"""
import sys
import json
from groq import Groq
from tools import list_files, read_file, write_file, grep

MODEL = "llama-3.3-70b-versatile"
MAX_TURNS = 40  # safety cap so a confused model can't loop forever

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List every file in the repository (relative paths).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of one file, given a path relative to the repo root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search every file for a regex pattern. Returns matching lines as 'path:line: text'.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file (relative to repo root) with new content. Creates parent dirs as needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Call once, when all changes are complete and verified. Ends the run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {"type": "string", "description": "The execution plan you followed."},
                    "summary": {"type": "string", "description": "Every file changed and why."},
                },
                "required": ["plan", "summary"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are an AI coding agent that improves an existing codebase to satisfy \
a product request, with minimal guidance beyond the request itself.

IMPORTANT: This is a plain JavaScript (CommonJS) project — there is no TypeScript build step.
All files you write or modify MUST use the .js extension and require()/module.exports syntax.
Never create .ts files. Never use import/export syntax.
Before creating a new file, check the extension of similar existing files in the same directory and match it exactly.

Follow this process:
1. EXPLORE first. Use list_files, grep, and read_file to understand the project's \
   architecture (frameworks, routing, models, existing conventions) before touching \
   anything. Read every file you are about to modify, in full, before modifying it.
2. Decide on a concrete, minimal EXECUTION PLAN: which files change, which are added, \
   and why this approach fits the existing architecture (naming, style, layering).
3. IMPLEMENT the plan using write_file. Match the existing code style. Do not remove or \
   break any existing functionality or API contract — only add to it.
4. When finished, call `finish` with the plan you followed and a summary of every file \
   you changed. You must call `finish` to end the run — do not just stop responding.

Be economical: don't re-read files you've already read unless you changed them.
"""


def run_agent(repo_path: str, request: str) -> None:
    client = Groq()  # reads GROQ_API_KEY from env
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Target repository path: {repo_path}\n\nProduct request: {request}",
        },
    ]

    for turn in range(MAX_TURNS):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=4096,
                tools=TOOLS,
                messages=messages,
            )
        except Exception as e:
            print(f"[warning] malformed tool call from model, retrying: {e}")
            messages.append(
                {
                    "role": "user",
                    "content": "Your last tool call was malformed (invalid JSON arguments or unknown tool). "
                    "Call the tool again with valid arguments as a proper JSON object.",
                }
            )
            continue
        message = response.choices[0].message
        messages.append(message)

        if message.content and message.content.strip():
            print(f"\n[agent reasoning] {message.content.strip()}\n")

        tool_calls = message.tool_calls or []
        if not tool_calls:
            messages.append({"role": "user", "content": "Continue. Call `finish` when done."})
            continue

        finished = False
        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}

            label = args.get("path", args.get("pattern", ""))
            print(f"[tool] {name} {label}")

            try:
                if name == "list_files":
                    result = "\n".join(list_files(repo_path))
                elif name == "read_file":
                    result = read_file(repo_path, args["path"])
                elif name == "grep":
                    result = "\n".join(grep(repo_path, args["pattern"])) or "(no matches)"
                elif name == "write_file":
                    result = write_file(repo_path, args["path"], args["content"])
                elif name == "finish":
                    print("\n=== EXECUTION PLAN ===\n" + args.get("plan", ""))
                    print("\n=== SUMMARY OF CHANGES ===\n" + args.get("summary", ""))
                    finished = True
                    result = "acknowledged"
                else:
                    result = f"ERROR: unknown tool {name}"
            except Exception as e:
                result = f"ERROR: {e}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": str(result)[:8000],
                }
            )

        if finished:
            return

    print("Stopped: hit MAX_TURNS without the agent calling finish.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python agent.py <repo_path> "<product request>"')
        sys.exit(1)
    run_agent(sys.argv[1], sys.argv[2])