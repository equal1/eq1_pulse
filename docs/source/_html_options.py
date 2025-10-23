# -- Options for HTML output -------------------------------------------------
from os import environ as _env

from _util import to_bool as _to_bool

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# some other themes  "pydata_sphinx_theme"  # "classic"  # "alabaster"

html_short_title = "eq1lab"
html_logo = "_static/eq1_pulse.svg"
html_favicon = "_static/eq1_pulse.svg"

DEFAULT_HTML_THEME = "furo"  # "sphinx_rtd_theme"

html_theme = str(_env.get("HTML_THEME", None) or DEFAULT_HTML_THEME)

html_static_path = ["_static"]

# The default html sidebar consists of 4 templates:
# ['localtoc.html', 'relations.html', 'sourcelink.html', 'searchbox.html']

html_css_files = []

if html_theme in {"sphinx_rtd_theme"}:
    html_sidebars = {
        "**": [
            # "localtoc.html",
            "globaltoc.html",
            "relations.html",
            "sourcelink.html",
            "searchbox.html",
        ]
    }

    html_css_files += ["rtd-custom.css"]

if html_theme in {"furo"}:
    # added #202020 to all default background colors
    html_theme_options = {
        "sidebar_hide_name": True,
        "dark_css_variables": {
            "color-foreground-primary": "#eff0f0",  # for main text and headings
            "color-foreground-secondary": "#bcc0c5",  # for secondary text
            "color-foreground-muted": "#a1a6ad",  # for muted text
            "color-foreground-border": "#868686",  # for content borders
            "color-background-secondary": "#3a3c3e",  # for navigation + ToC
            "color-background-primary": "#333436",  # for content
            "color-background-hover": "#3e4144ff",  # for navigation-item hover
            "color-background-hover--transparent": "#3e414400",
            "color-background-border": "#505355",  # for UI borders
            "color-background-item": "#444",  # for "background" items (eg: copybutton)
            "color-guilabel-background": "#28558380",
            "color-card-background": "#38383a",
            "color-admonition-background": "#38383a",
        },
    }
    html_css_files += [
        "furo-custom.css",
    ]

html_static_path += ["_css/" + file for file in html_css_files]

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".


html_show_sourcelink = _to_bool(_env.get("HTML_SHOW_SOURCELINK", False))
