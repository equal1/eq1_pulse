# sudo apt install fonts-lmodern fonts-cmu fonts-lato
# brew install mactex font-lato font-dejavu
latex_engine = "xelatex"
latex_elements = {
    # Clean out the legacy font encoding completely
    "fontenc": "",
    "fontpkg": "",
    "utf8extra": "",
    # Clean out font size
    "fvset": "",
    # untested ----
    "sphinxsetup": (
        # 1. Turn line wrapping on
        "verbatimwrapslines=true, "
        # 2. Fix the line-continuation hook (make it tiny and gray)
        r"verbatimcontinued={\tiny\color{gray}\hookrightarrow}, "
        # 3. Deal with the pre-newline whitespace marker:
        # OPTION A: Make it gray instead of red to match the hook
        r"verbatimvisiblespace={\tiny\color{gray}\textvisiblespace}, "
        # OPTION B: Alternatively, uncomment the line below to hide the marker entirely
        # r'verbatimvisiblespace={}, '
        # Add this line to scale down the code block font size globally
        r"verbatimwithframe=true, "
        # Adjust the border thickness here (try 1.5pt or 2pt for a thicker frame,
        # or 0.2pt for a hairline subtle look)
        r"verbatimborderwidth=1.5pt, "
        r"VerbatimColor={rgb}{0.98,0.98,0.98}, "
        r"VerbatimBorderColor={rgb}{0.8,0.8,0.8}, "
    ),
    # --- end untesed ---
    # Additional stuff for the LaTeX preamble.
    # The paper size ('letterpaper' or 'a4paper').
    "papersize": "a4paper",
    # The font size ('10pt', '11pt' or '12pt').
    "pointsize": "9pt",
    # Additional stuff for the LaTeX preamble.
    "preamble": r"""
            \usepackage{fontspec}"""
    # + r"\usepackage[EU1]{fontenc}"
    + r"""
            % Map main system fonts natively - commented out
            % \renewcommand\rmdefault{cmr}
            % \renewcommand\sfdefault{cmss}
            % \renewcommand\ttdefault{cmtt}

            \setmainfont{Lato}
            \setsansfont{Lato}
            \setmonofont{DejaVu Sans Mono}
            \usepackage{enumitem}
            \setlistdepth{99}

            % Lato (our main/sans font) doesn't cover every glyph we use in the
            % docs (e.g. some Greek letters, arrows, dingbats). newunicodechar
            % lets us route just those specific characters to a fallback font
            % with broader Unicode coverage, instead of switching the whole
            % document's font. DejaVu Sans is bundled with MiKTeX/most TeX
            % distributions, so this doesn't depend on an extra font install.
            \usepackage{newunicodechar}
            \newfontfamily{\unicodefallback}{DejaVu Sans}

            % Handle surgical Unicode fallbacks
            """
    + r"""
            """.join(
        r"""\newunicodechar{%s}{\unicodefallback %s}""" % (c, c)  # noqa: UP031
        # This is the actual list of characters, add new ones here
        for c in ("μ", "τ", "→", "↔", "✅", "❌")
    )
    + r"""

            % Silence layout spacing warnings
            \hbadness=10000
            \vbadness=10000

            % Font size for code blocks. Unfortunately
            % on Windows, anything except size 9pt is unsightly.
            \usepackage{etoolbox}
            \AtBeginEnvironment{sphinxVerbatim}{%
            \fontsize{9pt}{11pt}\selectfont
            }
        """,
}
