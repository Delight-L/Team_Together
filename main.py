"""WELFIND entry point: dashboard, preprocessing, analysis and chatbot."""
from pathlib import Path
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT_DIR / "agents" / "regional_analysis"

def main():
    arguments = sys.argv[1:]
    jobs = {
        "--preprocess-analysis1": ROOT_DIR / "preprocessing" / "regional_types" / "main.py",
        "--preprocess": ROOT_DIR / "preprocessing" / "regional_features" / "main.py",
        "--analysis": ANALYSIS_DIR / "main.py",
        "--risk": ROOT_DIR / "agents" / "risk_analysis" / "main.py",
        "--chatbot-cli": ROOT_DIR / "chatbot" / "data_assistant" / "main.py",
    }
    if arguments and arguments[0] in jobs:
        script = jobs[arguments[0]]
        path_flags = {"--input", "--context", "--output-dir", "--raw-dir", "--config", "--output", "--weather", "--compare"}
        for index in range(1, len(arguments)-1):
            if arguments[index] in path_flags:
                arguments[index+1] = str(Path(arguments[index+1]).resolve())
        raise SystemExit(subprocess.call([sys.executable, "-X", "utf8", str(script), *arguments[1:]], cwd=script.parent))
    from webapp.server import main as serve_react
    serve_react(arguments)

if __name__ == "__main__":
    main()
