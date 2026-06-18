import base64
from html import escape

import streamlit as st

from config import BASE_DIR


def _background_css_value() -> str:
    image_path = BASE_DIR / "assets" / "bg.png"
    if not image_path.exists():
        return (
            "radial-gradient(circle at 18% 12%, rgba(103, 232, 249, 0.22), transparent 28%),"
            "radial-gradient(circle at 80% 8%, rgba(167, 139, 250, 0.22), transparent 32%),"
            "linear-gradient(135deg, #040614 0%, #071022 48%, #10091e 100%)"
        )
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return (
        "linear-gradient(135deg, rgba(3, 7, 18, 0.46), rgba(3, 7, 18, 0.68)), "
        f'url("data:image/png;base64,{encoded}")'
    )


def apply_modern_theme() -> None:
    css = """
        <style>
        :root {
            --bg: #050816;
            --bg-2: #0b1023;
            --glass: rgba(12, 18, 38, 0.44);
            --glass-strong: rgba(15, 23, 42, 0.68);
            --line: rgba(255, 255, 255, 0.14);
            --line-hot: rgba(125, 211, 252, 0.56);
            --ink: #f8fafc;
            --muted: #aab6ca;
            --brand: #67e8f9;
            --brand-2: #a78bfa;
            --brand-3: #fb7185;
            --ok: #5eead4;
            --shadow: 0 26px 80px rgba(0, 0, 0, 0.38);
            --radius: 18px;
            --rail-width: 64px;
        }

        .stApp {
            color: var(--ink);
            background: __APP_BACKGROUND__;
            background-size: cover;
            background-position: center center;
            background-attachment: fixed;
        }

        .stApp:before {
            display: none;
        }

        .block-container {
            max-width: 1120px;
            padding-top: 1.35rem;
            padding-bottom: 3rem;
            padding-left: max(1.4rem, calc(var(--rail-width) + 0.5rem));
            padding-right: 2rem;
            position: relative;
            z-index: 1;
        }

        h1, h2, h3, h4, h5, h6, p, label, span, div {
            letter-spacing: 0;
        }

        h1, h2, h3, h4, h5, h6,
        [data-testid="stMarkdownContainer"],
        [data-testid="stText"] {
            color: var(--ink);
        }

        p, .stCaptionContainer, small {
            color: var(--muted);
        }

        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"] {
            display: none;
        }

        /* Thin left heading rail. It expands on hover so Streamlit's native page nav and page settings remain usable. */
        section[data-testid="stSidebar"] {
            width: var(--rail-width) !important;
            min-width: var(--rail-width) !important;
            background: rgba(5, 8, 22, 0.52);
            border-right: 1px solid rgba(255, 255, 255, 0.10);
            box-shadow: 20px 0 70px rgba(0, 0, 0, 0.30);
            backdrop-filter: blur(18px);
            transition: width 220ms ease, min-width 220ms ease, background 220ms ease;
            overflow: hidden;
        }

        section[data-testid="stSidebar"]:after {
            content: "MC";
            position: absolute;
            top: 22px;
            left: 14px;
            width: 36px;
            height: 36px;
            display: grid;
            place-items: center;
            border-radius: 8px;
            font-weight: 900;
            color: #06111f;
            background: linear-gradient(135deg, var(--brand), var(--brand-2), var(--brand-3));
            box-shadow: 0 0 32px rgba(103, 232, 249, 0.34);
            z-index: 3;
        }

        section[data-testid="stSidebar"]:hover,
        section[data-testid="stSidebar"]:focus-within {
            width: 196px !important;
            min-width: 196px !important;
            background: rgba(5, 8, 22, 0.72);
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding-top: 78px;
            opacity: 0;
            transform: translateX(-10px);
            pointer-events: none;
            transition: opacity 180ms ease, transform 180ms ease;
        }

        section[data-testid="stSidebar"]:hover [data-testid="stSidebarUserContent"],
        section[data-testid="stSidebar"]:focus-within [data-testid="stSidebarUserContent"] {
            opacity: 1;
            transform: translateX(0);
            pointer-events: auto;
        }

        section[data-testid="stSidebar"] a,
        section[data-testid="stSidebar"] button,
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {
            color: var(--ink) !important;
        }

        .page-title,
        .section-card,
        .metric-card,
        .bento-card,
        .source-row,
        div[data-testid="stExpander"] {
            border: 0 !important;
            background: rgba(255, 255, 255, 0.16) !important;
            box-shadow: 0 24px 70px rgba(0, 0, 0, 0.24);
            backdrop-filter: blur(20px) saturate(1.18);
            position: relative;
        }

        div[data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stForm"] {
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            backdrop-filter: none !important;
        }

        .platform-hero {
            margin: 12px 0 30px;
            padding: 8px 0 4px;
            background: transparent;
            border: 0;
            box-shadow: none;
        }

        .platform-hero h1 {
            margin: 0;
            font-size: clamp(62px, 10vw, 116px);
            line-height: 1;
            font-weight: 950;
            font-family: "Lucida Calligraphy", "Segoe UI Black", "Arial Black", Impact, "Trebuchet MS", sans-serif;
            letter-spacing: 0;
            color: transparent;
            background:
                linear-gradient(110deg, rgba(255, 255, 255, 0.88) 0%, rgba(207, 250, 254, 0.82) 34%, rgba(233, 213, 255, 0.78) 68%, rgba(255, 228, 230, 0.76) 100%);
            -webkit-background-clip: text;
            background-clip: text;
            filter: drop-shadow(0 18px 46px rgba(255, 255, 255, 0.10));
            opacity: 0.94;
        }

        .platform-hero p {
            max-width: 760px;
            margin: 18px 0 0;
            color: #cbd5e1;
            font-size: 17px;
            line-height: 1.75;
        }

        .feature-chip {
            min-height: 104px;
            padding: 14px 16px 13px;
            border-radius: var(--radius);
            border: 0;
            background: rgba(255, 255, 255, 0.18);
            box-shadow: 0 18px 54px rgba(0, 0, 0, 0.22);
            backdrop-filter: blur(20px) saturate(1.18);
            transition: transform 170ms ease, box-shadow 170ms ease, filter 170ms ease;
            position: relative;
            overflow: hidden;
        }

        .feature-chip:hover {
            transform: translateY(-3px);
            box-shadow: 0 26px 76px rgba(0, 0, 0, 0.40), 0 0 30px rgba(103, 232, 249, 0.12);
            filter: saturate(1.08);
        }

        .feature-chip:after,
        .section-card:after,
        .metric-card:after,
        .bento-card:after,
        .source-row:after,
        .page-title:after,
        div[data-testid="stExpander"]:after {
            content: "";
            position: absolute;
            inset: 0;
            padding: 1px;
            border-radius: inherit;
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.26) 38%, rgba(255, 255, 255, 0.00) 72%);
            opacity: 0;
            pointer-events: none;
            transition: opacity 180ms ease;
            -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
        }

        .feature-chip:hover:after,
        .section-card:hover:after,
        .metric-card:hover:after,
        .bento-card:hover:after,
        .source-row:hover:after,
        .page-title:hover:after,
        div[data-testid="stExpander"]:hover:after {
            opacity: 1;
        }

        .feature-chip .feature-icon {
            width: 28px;
            height: 28px;
            display: grid;
            place-items: center;
            border-radius: 10px;
            margin-bottom: 10px;
            color: #06111f;
            background: linear-gradient(135deg, var(--brand), var(--brand-2));
            font-weight: 900;
        }

        .feature-chip h3 {
            margin: 0 0 5px;
            font-size: 16px;
            color: var(--ink);
        }

        .feature-chip p {
            margin: 0;
            color: var(--muted);
            line-height: 1.42;
            font-size: 12px;
        }

        .feature-spacer {
            height: 16px;
        }

        .page-title {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            align-items: start;
            gap: 22px;
            padding: 28px 30px;
            border-radius: var(--radius);
            margin-bottom: 22px;
            position: relative;
            overflow: hidden;
        }

        .page-title:before {
            content: "";
            position: absolute;
            inset: -40%;
            background:
                radial-gradient(circle, rgba(103, 232, 249, 0.16), transparent 30%),
                radial-gradient(circle at 80% 20%, rgba(167, 139, 250, 0.16), transparent 28%);
            animation: slowSpin 16s linear infinite;
            pointer-events: none;
        }

        @keyframes slowSpin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .page-title > * {
            position: relative;
            z-index: 1;
        }

        .page-title h1 {
            margin: 0;
            font-size: 38px;
            line-height: 1.05;
            color: var(--ink);
        }

        .page-title p {
            margin: 10px 0 0;
            color: var(--muted);
            font-size: 15px;
            line-height: 1.65;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            padding: 7px 11px;
            border-radius: 999px;
            color: var(--ink);
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(103, 232, 249, 0.32);
            box-shadow: 0 0 24px rgba(103, 232, 249, 0.12);
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
        }

        .section-card,
        .metric-card,
        .bento-card,
        .source-row {
            border-radius: var(--radius);
            padding: 18px;
            margin-bottom: 16px;
            transition: transform 170ms ease, box-shadow 170ms ease, filter 170ms ease;
        }

        .section-card:hover,
        .metric-card:hover,
        .bento-card:hover,
        .source-row:hover {
            transform: translateY(-3px);
            box-shadow: 0 30px 90px rgba(0, 0, 0, 0.46), 0 0 34px rgba(103, 232, 249, 0.12);
            filter: saturate(1.08);
        }

        .bento-card {
            min-height: 164px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .bento-card.large {
            min-height: 252px;
        }

        .bento-kicker {
            color: var(--brand);
            font-size: 12px;
            font-weight: 900;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .bento-card h3 {
            color: var(--ink);
            font-size: 22px;
            margin: 0 0 10px;
        }

        .bento-card p,
        .section-card p {
            color: var(--muted);
            margin: 0;
            line-height: 1.68;
        }

        .metric-card {
            min-height: 98px;
        }

        .metric-card .label {
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 7px;
        }

        .metric-card .value {
            color: var(--ink);
            font-size: 27px;
            line-height: 1.15;
            font-weight: 900;
            overflow-wrap: anywhere;
        }

        .source-row {
            padding: 14px 15px;
        }

        .source-row strong {
            display: block;
            color: var(--ink);
            font-size: 14px;
            margin-bottom: 5px;
        }

        .source-row span {
            color: var(--muted);
            font-size: 12px;
        }

        div[data-testid="stTextArea"] textarea,
        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"],
        div[data-baseweb="input"] > div,
        div[data-baseweb="base-input"],
        div[data-baseweb="input"] input,
        input {
            color: var(--ink) !important;
            background-color: rgba(255, 255, 255, 0.055) !important;
            background: rgba(255, 255, 255, 0.055) !important;
            border-color: rgba(255, 255, 255, 0.16) !important;
            border-radius: var(--radius) !important;
        }

        div[data-testid="stForm"] {
            padding: 0;
            border-radius: var(--radius);
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
        }

        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stTextInput"] input:focus {
            border-color: rgba(103, 232, 249, 0.64) !important;
            box-shadow: 0 0 0 1px rgba(103, 232, 249, 0.32), 0 0 32px rgba(103, 232, 249, 0.11) !important;
        }

        /* Control-level glass polish: keep inputs as metric-card style glass, without touching layout containers. */
        div[data-baseweb="textarea"],
        div[data-testid="stFileUploader"] section,
        [data-testid="stFileUploaderDropzone"],
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            color: var(--ink) !important;
            border: 0 !important;
            border-radius: var(--radius) !important;
            background: rgba(255, 255, 255, 0.16) !important;
            background-color: rgba(255, 255, 255, 0.16) !important;
            box-shadow: 0 24px 70px rgba(0, 0, 0, 0.24) !important;
            backdrop-filter: blur(20px) saturate(1.18) !important;
            overflow: hidden !important;
        }

        div[data-baseweb="textarea"] > div,
        div[data-testid="stTextArea"] textarea,
        [data-testid="stFileUploaderDropzone"] > div {
            color: var(--ink) !important;
            border: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none !important;
        }

        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="textarea"] textarea {
            min-height: inherit;
            color: var(--ink) !important;
            background: transparent !important;
            background-color: transparent !important;
            -webkit-text-fill-color: var(--ink) !important;
            caret-color: var(--brand) !important;
        }

        div[data-testid="stTextArea"] textarea::placeholder,
        div[data-baseweb="textarea"] textarea::placeholder,
        div[data-testid="stTextInput"] input::placeholder,
        div[data-baseweb="input"] input::placeholder {
            color: rgba(255, 255, 255, 0.88) !important;
            -webkit-text-fill-color: rgba(255, 255, 255, 0.88) !important;
            opacity: 1 !important;
        }

        div[data-testid="stFileUploader"] section *,
        [data-testid="stFileUploaderDropzone"] *,
        div[data-testid="stSelectbox"] [data-baseweb="select"] * {
            color: var(--ink) !important;
        }

        div[data-testid="stFileUploader"] button,
        [data-testid="stFileUploaderDropzone"] button {
            color: var(--ink) !important;
            border: 0 !important;
            border-radius: calc(var(--radius) - 4px) !important;
            background: rgba(255, 255, 255, 0.16) !important;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.14) !important;
        }

        div[data-baseweb="popover"] > div,
        div[data-baseweb="menu"],
        div[data-baseweb="menu"] ul,
        ul[role="listbox"] {
            color: var(--ink) !important;
            border: 0 !important;
            background: rgba(255, 255, 255, 0.16) !important;
            box-shadow: 0 24px 70px rgba(0, 0, 0, 0.24) !important;
            backdrop-filter: blur(20px) saturate(1.18) !important;
        }

        li[role="option"],
        div[role="option"] {
            color: var(--ink) !important;
            background: transparent !important;
            box-shadow: none !important;
        }

        div[data-baseweb="popover"] > div,
        div[data-baseweb="menu"],
        ul[role="listbox"] {
            border-radius: var(--radius) !important;
            overflow: hidden !important;
        }

        li[role="option"]:hover,
        div[role="option"]:hover,
        li[aria-selected="true"],
        div[aria-selected="true"] {
            background: rgba(255, 255, 255, 0.14) !important;
        }

        /* BaseWeb renders select dropdowns in a portal, so the action-board status menu needs stronger glass rules. */
        body div[data-baseweb="popover"],
        body div[data-baseweb="popover"] > div,
        body div[data-baseweb="select-dropdown"],
        body div[data-baseweb="menu"],
        body div[data-baseweb="menu"] ul,
        body div[role="listbox"],
        body ul[role="listbox"] {
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
            border: 0 !important;
            border-radius: var(--radius) !important;
            background: rgba(255, 255, 255, 0.16) !important;
            background-color: rgba(255, 255, 255, 0.16) !important;
            box-shadow: 0 24px 70px rgba(0, 0, 0, 0.24) !important;
            backdrop-filter: blur(20px) saturate(1.18) !important;
            overflow: hidden !important;
        }

        body div[data-baseweb="popover"] li,
        body div[data-baseweb="popover"] li *,
        body div[data-baseweb="popover"] div[role="option"],
        body div[data-baseweb="popover"] div[role="option"] *,
        body div[data-baseweb="select-dropdown"] li,
        body div[data-baseweb="select-dropdown"] li *,
        body div[data-baseweb="select-dropdown"] div,
        body div[data-baseweb="select-dropdown"] span,
        body ul[role="listbox"] li,
        body ul[role="listbox"] li *,
        body div[role="listbox"] div,
        body div[role="listbox"] span {
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
            background: transparent !important;
            background-color: transparent !important;
        }

        body div[data-baseweb="popover"] li:hover,
        body div[data-baseweb="popover"] div[role="option"]:hover,
        body div[data-baseweb="select-dropdown"] li:hover,
        body div[data-baseweb="select-dropdown"] div[role="option"]:hover,
        body ul[role="listbox"] li:hover,
        body div[role="listbox"] div[role="option"]:hover,
        body div[data-baseweb="popover"] div[aria-selected="true"],
        body div[data-baseweb="popover"] li[aria-selected="true"],
        body div[data-baseweb="select-dropdown"] div[aria-selected="true"],
        body div[data-baseweb="select-dropdown"] li[aria-selected="true"] {
            background: rgba(255, 255, 255, 0.18) !important;
            background-color: rgba(255, 255, 255, 0.18) !important;
        }

        div.stButton > button,
        div.stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] button,
        button[kind="primary"],
        button[data-testid="stBaseButton-primary"],
        a[data-testid="stPageLink-NavLink"] {
            border-radius: var(--radius) !important;
            font-weight: 800 !important;
            color: var(--ink) !important;
            background:
                linear-gradient(135deg, rgba(103, 232, 249, 0.22), rgba(167, 139, 250, 0.16)) padding-box,
                linear-gradient(135deg, rgba(103, 232, 249, 0.78), rgba(167, 139, 250, 0.52)) border-box !important;
            border: 1px solid transparent !important;
            transition: transform 150ms ease, box-shadow 150ms ease, filter 150ms ease;
        }

        div.stButton > button:hover,
        div.stDownloadButton > button:hover,
        div[data-testid="stFormSubmitButton"] button:hover,
        button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover,
        a[data-testid="stPageLink-NavLink"]:hover {
            transform: translateY(-2px) scale(1.01);
            box-shadow: 0 16px 42px rgba(103, 232, 249, 0.18);
            filter: brightness(1.14);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: var(--radius);
            padding: 6px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: var(--radius);
            padding: 10px 14px;
            color: var(--muted);
            background: transparent;
        }

        .stTabs [aria-selected="true"] {
            color: var(--ink);
            background: rgba(255, 255, 255, 0.10);
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border-radius: var(--radius);
            overflow: hidden;
        }

        .skeleton-card {
            border-radius: var(--radius);
            padding: 18px;
            background: rgba(255, 255, 255, 0.16);
            border: 0;
            box-shadow: 0 24px 70px rgba(0, 0, 0, 0.24);
            backdrop-filter: blur(20px) saturate(1.18);
            margin-bottom: 16px;
        }

        .skeleton-line,
        .skeleton-block {
            border-radius: var(--radius);
            background: linear-gradient(90deg, rgba(255,255,255,0.08) 25%, rgba(103,232,249,0.22) 37%, rgba(255,255,255,0.08) 63%);
            background-size: 400% 100%;
            animation: skeletonShimmer 1.25s ease-in-out infinite;
        }

        .skeleton-line {
            height: 14px;
            margin-bottom: 12px;
        }

        .skeleton-block {
            height: 112px;
            margin-top: 16px;
        }

        @keyframes skeletonShimmer {
            0% { background-position: 100% 0; }
            100% { background-position: 0 0; }
        }

        div[data-testid="stAlert"] {
            background: rgba(12, 18, 38, 0.62);
            border-radius: var(--radius);
            border: 1px solid rgba(255, 255, 255, 0.14);
            color: var(--ink);
        }

        hr {
            border-color: rgba(255, 255, 255, 0.12);
        }

        code, pre {
            color: #dffcff !important;
            background: rgba(255, 255, 255, 0.06) !important;
            border-radius: var(--radius) !important;
        }

        div[data-testid="stStatusWidget"] {
            background: rgba(255, 255, 255, 0.16) !important;
            border: 0 !important;
            border-radius: 999px !important;
            box-shadow: 0 18px 46px rgba(0, 0, 0, 0.24);
            backdrop-filter: blur(18px) saturate(1.14);
            color: var(--ink) !important;
        }

        div[data-testid="stStatusWidget"] * {
            color: var(--ink) !important;
        }

        div[data-testid="stSpinner"] {
            width: fit-content;
            max-width: min(520px, 100%);
            padding: 14px 18px;
            border-radius: var(--radius);
            background: rgba(255, 255, 255, 0.16);
            box-shadow: 0 20px 58px rgba(0, 0, 0, 0.25);
            backdrop-filter: blur(20px) saturate(1.18);
        }

        div[data-testid="stSpinner"] *,
        div[data-testid="stSpinner"] p {
            color: var(--ink) !important;
        }

        div[data-testid="stSpinner"] svg {
            color: rgba(255, 255, 255, 0.88) !important;
            fill: rgba(255, 255, 255, 0.88) !important;
        }

        div[data-testid="stProgress"] > div {
            background: rgba(255, 255, 255, 0.12) !important;
            border-radius: 999px !important;
            overflow: hidden;
        }

        div[data-testid="stProgress"] div[role="progressbar"],
        div[data-testid="stProgress"] > div > div > div {
            background: linear-gradient(90deg, rgba(255, 255, 255, 0.90), rgba(207, 250, 254, 0.78), rgba(233, 213, 255, 0.72)) !important;
        }

        div[data-testid="stSkeleton"],
        [data-testid="stSkeleton"] div {
            border-radius: var(--radius) !important;
            background: linear-gradient(90deg, rgba(255,255,255,0.10) 25%, rgba(255,255,255,0.28) 37%, rgba(255,255,255,0.10) 63%) !important;
            background-size: 400% 100% !important;
            animation: skeletonShimmer 1.25s ease-in-out infinite !important;
        }

        @media (max-width: 860px) {
            :root { --rail-width: 0px; }
            section[data-testid="stSidebar"] {
                width: 0 !important;
                min-width: 0 !important;
                display: none;
            }
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }
            .page-title {
                grid-template-columns: 1fr;
                padding: 22px;
            }
            .page-title h1 {
                font-size: 30px;
            }
            .platform-hero h1 {
                font-size: 54px;
            }
            .bento-card,
            .bento-card.large {
                min-height: auto;
            }
        }
        </style>
        """
    css = css.replace("__APP_BACKGROUND__", _background_css_value())
    st.markdown(
        css,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str, pill: str | None = None) -> None:
    pill_html = f'<span class="status-pill">{escape(pill)}</span>' if pill else ""
    st.markdown(
        f"""
        <div class="page-title">
            <div>
                <h1>{escape(title)}</h1>
                <p>{escape(subtitle)}</p>
            </div>
            {pill_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="label">{escape(label)}</div>
            <div class="value">{escape(str(value))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def platform_hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="platform-hero">
            <h1>{escape(title)}</h1>
            <p>{escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def feature_chip(icon: str, title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="feature-chip">
            <div class="feature-icon">{escape(icon)}</div>
            <h3>{escape(title)}</h3>
            <p>{escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def bento_card(kicker: str, title: str, body: str, large: bool = False) -> None:
    size_class = " large" if large else ""
    st.markdown(
        f"""
        <div class="bento-card{size_class}">
            <div>
                <div class="bento-kicker">{escape(kicker)}</div>
                <h3>{escape(title)}</h3>
                <p>{escape(body)}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def skeleton_loader(title: str = "正在生成结构化纪要") -> str:
    return f"""
    <div class="skeleton-card">
        <div class="bento-kicker">{escape(title)}</div>
        <div class="skeleton-line" style="width: 64%;"></div>
        <div class="skeleton-line" style="width: 92%;"></div>
        <div class="skeleton-line" style="width: 76%;"></div>
        <div class="skeleton-block"></div>
    </div>
    """
