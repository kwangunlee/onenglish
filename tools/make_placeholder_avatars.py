"""
임시 캐릭터 아바타 생성기.

Flow(Veo)로 만든 진짜 캐릭터 이미지가 준비되기 전까지 쓸 자리표시용 그림을
만듭니다. 나중에 assets/luna.png 등을 Flow 로 만든 파일로 그냥 덮어쓰면 됩니다.
파일 이름만 같으면 앱 코드는 수정할 필요가 없습니다.

실행:
    python tools/make_placeholder_avatars.py

rsvg-convert 또는 cairosvg 가 있으면 PNG 로, 없으면 SVG 로만 남깁니다.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZE = 512


def svg(parts: list[str], bg1: str, bg2: str) -> str:
    body = "\n".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" viewBox="0 0 512 512">
<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
<stop offset="0%" stop-color="{bg1}"/><stop offset="100%" stop-color="{bg2}"/>
</linearGradient></defs>
<rect width="512" height="512" rx="56" fill="url(#bg)"/>
{body}
</svg>"""


def eyes(cx: float, cy: float, dx: float, r: float = 17) -> str:
    out = []
    for sign in (-1, 1):
        x = cx + sign * dx
        out.append(f'<circle cx="{x}" cy="{cy}" r="{r}" fill="#2C2C2A"/>')
        out.append(f'<circle cx="{x + 5}" cy="{cy - 6}" r="{r / 2.9:.1f}" fill="#fff"/>')
    return "".join(out)


def smile(cx: float, cy: float, w: float, stroke: str = "#2C2C2A") -> str:
    return (f'<path d="M{cx - w} {cy} Q{cx} {cy + w * 0.72} {cx + w} {cy}" '
            f'fill="none" stroke="{stroke}" stroke-width="7" stroke-linecap="round"/>')


def blush(cx: float, cy: float, dx: float, color: str) -> str:
    return "".join(
        f'<ellipse cx="{cx + s * dx}" cy="{cy}" rx="22" ry="13" '
        f'fill="{color}" opacity="0.55"/>'
        for s in (-1, 1)
    )


# ── Luna — 별빛 요정 ─────────────────────────────────────────────
LUNA = svg([
    # 날개
    '<ellipse cx="108" cy="250" rx="58" ry="96" fill="#CECBF6" opacity="0.8" transform="rotate(-24 108 250)"/>',
    '<ellipse cx="404" cy="250" rx="58" ry="96" fill="#CECBF6" opacity="0.8" transform="rotate(24 404 250)"/>',
    '<ellipse cx="128" cy="330" rx="40" ry="62" fill="#CECBF6" opacity="0.6" transform="rotate(-34 128 330)"/>',
    '<ellipse cx="384" cy="330" rx="40" ry="62" fill="#CECBF6" opacity="0.6" transform="rotate(34 384 330)"/>',
    # 몸
    '<path d="M256 300 Q196 312 182 420 L330 420 Q316 312 256 300 Z" fill="#AFA9EC"/>',
    # 얼굴
    '<circle cx="256" cy="226" r="106" fill="#FBE6D4"/>',
    # 머리카락
    '<path d="M150 214 Q158 104 256 104 Q354 104 362 214 Q334 170 256 170 Q178 170 150 214 Z" fill="#D8D4F5"/>',
    '<path d="M150 214 Q132 266 146 310 Q166 268 160 220 Z" fill="#D8D4F5"/>',
    '<path d="M362 214 Q380 266 366 310 Q346 268 352 220 Z" fill="#D8D4F5"/>',
    eyes(256, 232, 38),
    smile(256, 272, 26),
    blush(256, 262, 72, "#F4C0D1"),
    # 별 왕관
    '<path d="M256 76 l11 24 26 3 -19 18 5 26 -23-13 -23 13 5-26 -19-18 26-3 Z" fill="#FAC775"/>',
    # 반짝임
    '<circle cx="98" cy="150" r="7" fill="#fff" opacity="0.9"/>',
    '<circle cx="424" cy="186" r="5" fill="#fff" opacity="0.8"/>',
    '<circle cx="408" cy="104" r="8" fill="#fff" opacity="0.7"/>',
], "#EEEDFE", "#CECBF6")

# ── Rocky — 구조견 ───────────────────────────────────────────────
ROCKY = svg([
    # 귀
    '<ellipse cx="140" cy="276" rx="33" ry="72" fill="#A9712F" transform="rotate(-10 140 276)"/>',
    '<ellipse cx="372" cy="276" rx="33" ry="72" fill="#A9712F" transform="rotate(10 372 276)"/>',
    # 조끼
    '<path d="M256 306 Q192 320 178 424 L334 424 Q320 320 256 306 Z" fill="#378ADD"/>',
    '<circle cx="256" cy="372" r="24" fill="#FAC775"/>',
    '<path d="M256 358 l5 11 12 1 -9 8 2 12 -10-6 -10 6 2-12 -9-8 12-1 Z" fill="#854F0B"/>',
    # 얼굴
    '<circle cx="256" cy="232" r="104" fill="#C98B46"/>',
    # 이마 무늬
    '<path d="M256 128 Q222 140 214 170 Q256 158 298 170 Q290 140 256 128 Z" fill="#F0DCC0"/>',
    # 주둥이
    '<ellipse cx="256" cy="278" rx="62" ry="48" fill="#F0DCC0"/>',
    '<ellipse cx="256" cy="256" rx="19" ry="14" fill="#2C2C2A"/>',
    smile(256, 290, 24),
    eyes(256, 214, 40),
], "#E6F1FB", "#B5D4F4")

# ── Zoom — 레이싱 카 ─────────────────────────────────────────────
ZOOM = svg([
    # 스피드 라인
    '<rect x="40" y="208" width="54" height="9" rx="4" fill="#fff" opacity="0.75"/>',
    '<rect x="56" y="234" width="38" height="9" rx="4" fill="#fff" opacity="0.6"/>',
    # 바퀴
    '<circle cx="138" cy="382" r="48" fill="#2C2C2A"/><circle cx="138" cy="382" r="20" fill="#B4B2A9"/>',
    '<circle cx="374" cy="382" r="48" fill="#2C2C2A"/><circle cx="374" cy="382" r="20" fill="#B4B2A9"/>',
    # 차체
    '<path d="M104 372 Q96 290 150 268 L362 268 Q416 290 408 372 Z" fill="#D85A30"/>',
    # 레이싱 스트라이프
    '<rect x="238" y="268" width="36" height="104" fill="#F1EFE8" opacity="0.9"/>',
    # 캐노피(앞유리)
    '<path d="M166 268 Q186 182 256 182 Q326 182 346 268 Z" fill="#B5D4F4"/>',
    eyes(256, 230, 40, 19),
    smile(256, 252, 20, "#185FA5"),
    # 번호판
    '<circle cx="256" cy="330" r="27" fill="#F1EFE8"/>',
    '<text x="256" y="344" font-family="Arial,sans-serif" font-size="38" font-weight="bold" fill="#D85A30" text-anchor="middle">1</text>',
], "#FAECE7", "#F5C4B3")

# ── Mochi — 곰돌이 ───────────────────────────────────────────────
MOCHI = svg([
    # 귀
    '<circle cx="158" cy="156" r="52" fill="#E8D5BE"/><circle cx="158" cy="156" r="27" fill="#F4C0D1"/>',
    '<circle cx="354" cy="156" r="52" fill="#E8D5BE"/><circle cx="354" cy="156" r="27" fill="#F4C0D1"/>',
    # 몸
    '<path d="M256 308 Q186 322 174 426 L338 426 Q326 322 256 308 Z" fill="#E8D5BE"/>',
    # 얼굴
    '<circle cx="256" cy="234" r="110" fill="#F2E2CC"/>',
    # 주둥이
    '<ellipse cx="256" cy="282" rx="56" ry="42" fill="#FBF2E4"/>',
    '<ellipse cx="256" cy="262" rx="16" ry="12" fill="#B07A5A"/>',
    smile(256, 292, 22, "#B07A5A"),
    eyes(256, 222, 42),
    blush(256, 262, 80, "#F4C0D1"),
    # 리본
    '<path d="M256 136 l-42 -24 0 44 Z" fill="#ED93B1"/>',
    '<path d="M256 136 l42 -24 0 44 Z" fill="#ED93B1"/>',
    '<circle cx="256" cy="136" r="14" fill="#D4537E"/>',
], "#FBEAF0", "#F4C0D1")

CHARACTERS = {"luna": LUNA, "rocky": ROCKY, "zoom": ZOOM, "mochi": MOCHI}


def to_png(svg_path: Path, png_path: Path) -> bool:
    if shutil.which("rsvg-convert"):
        r = subprocess.run(
            ["rsvg-convert", "-w", str(SIZE), "-h", str(SIZE),
             "-o", str(png_path), str(svg_path)],
            capture_output=True,
        )
        if r.returncode == 0:
            return True
    try:
        import cairosvg
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path),
                         output_width=SIZE, output_height=SIZE)
        return True
    except Exception:
        return False


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    made = []
    for name, markup in CHARACTERS.items():
        svg_path = ASSETS / f"{name}.svg"
        svg_path.write_text(markup, encoding="utf-8")
        png_path = ASSETS / f"{name}.png"
        if to_png(svg_path, png_path):
            made.append(png_path.name)
        else:
            made.append(f"{svg_path.name} (PNG 변환 실패 — SVG 만 생성)")
    print("생성 완료:", ", ".join(made))
    print(f"위치: {ASSETS}")
    print("\nFlow 로 만든 이미지로 바꾸려면 같은 파일명으로 덮어쓰면 됩니다.")
    print("각 캐릭터의 Flow 프롬프트는 data/packs/kids/characters.json 의")
    print("flow_prompt 항목에 들어있습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
