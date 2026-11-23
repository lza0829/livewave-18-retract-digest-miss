from pathlib import Path

根 = Path(__file__).resolve().parent


def _首个说明(text: str) -> str:
    if '"""' not in text:
        return ""
    body = text.split('"""')[1].strip()
    return body.splitlines()[0].strip() if body else ""


def 列表() -> list:
    out = []
    for p in sorted(根.iterdir()):
        if p.is_dir() and not p.name.startswith("_"):
            init = p / "__init__.py"
            状态 = "未实现"
            说明 = ""
            if init.exists():
                text = init.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.startswith("状态"):
                        状态 = line.split("=", 1)[-1].strip().strip("\"'")
            if init.exists():
                说明 = _首个说明(text)
            out.append({"名": p.name, "状态": 状态, "说明": 说明})
    return out
