import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "ARABIC_GUIDE.md"
CHANGELOG = ROOT / "docs" / "CHANGELOG_AR.md"
REQUIRED_GUIDE_SECTIONS = (
    "ما هو Stock Hunter؟",
    "كيف تتحرك البيانات داخل النظام؟",
    "ما الذي لا يفعله النظام؟",
    "قاعدة تحديث هذا الدليل",
)


def changed_files() -> set[str]:
    if not os.getenv("CI"):
        return set()
    base_ref = os.getenv("GITHUB_BASE_REF")
    if base_ref:
        subprocess.run(
            ["git", "fetch", "origin", base_ref, "--depth=1"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        base = subprocess.check_output(
            ["git", "merge-base", "HEAD", f"origin/{base_ref}"], cwd=ROOT, text=True
        ).strip()
    else:
        try:
            base = subprocess.check_output(
                ["git", "rev-parse", "HEAD^"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
            ).strip()
        except subprocess.CalledProcessError:
            return set()
    output = subprocess.check_output(
        ["git", "diff", "--name-only", base, "HEAD"], cwd=ROOT, text=True
    )
    return {line for line in output.splitlines() if line}


def main() -> None:
    missing = [str(path.relative_to(ROOT)) for path in (GUIDE, CHANGELOG) if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required documentation: {', '.join(missing)}")
    guide = GUIDE.read_text(encoding="utf-8")
    absent_sections = [section for section in REQUIRED_GUIDE_SECTIONS if section not in guide]
    if absent_sections:
        raise SystemExit(f"Arabic guide is incomplete: {', '.join(absent_sections)}")

    changed = changed_files()
    product_change = any(
        path.startswith("src/stock_hunter/")
        or path in {".env.example", "Dockerfile", "docker-compose.yml", "pyproject.toml"}
        for path in changed
    )
    docs_changed = {"docs/ARABIC_GUIDE.md", "docs/CHANGELOG_AR.md"}.issubset(changed)
    if product_change and not docs_changed:
        raise SystemExit(
            "Product behavior changed without updating both Arabic documentation files."
        )
    print("Arabic documentation check passed")


if __name__ == "__main__":
    main()
