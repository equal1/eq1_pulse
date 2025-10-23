# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# ruff: noqa: D100 # undocumented-public-module
# ruff: noqa: F403 # undefined-local-with-import-star
# ruff: noqa: E501 # line-too-long

import os
import sys

# -- Path setup --------------------------------------------------------------
sys.path.insert(0, ".")
from _autoapi_ignore import *
from _autodoc_type_aliases import *
from _html_options import *
from _intersphinx_options import *
from _latex_options import *
from _util import git_version as _git_version  # noqa: F401
from _util import to_bool as _to_bool

del sys.path[0]

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


sys.path.insert(0, os.path.abspath("../../src"))

project = "eq1_pulse"
copyright = "2025, Equal1"
author = "Equal1"
release = "0.0.1"

# version = _git_version()
# release = _git_version()

html_title = f"{project}"


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    # "sphinx.ext.autosummary",
    "sphinx.ext.graphviz",
    "sphinx.ext.inheritance_diagram",
    "autoapi.extension",
    "sphinx.ext.autodoc.typehints",
    # "matplotlib.sphinxext.plot_directive",
    "sphinx.ext.mathjax",
    "sphinx.ext.todo",
    "sphinx.ext.githubpages",
    "sphinx_tabs.tabs",
    "myst_parser",
]

# these might not be necessary
myst_enable_extensions = [
    "dollarmath",  # for parsing of dollar $ and $$ encapsulated math.
    "smartquotes",  # convert standard quotations to their opening/closing variants
    "replacements",  # automatically convert some common typographic texts
    "colon_fence",  #  Code fences using colons
]
# myst_update_mathjax = False
myst_heading_anchors = 5

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates", "_templates/autoapi"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []  # type: ignore

pygments_style = "sphinx"


# -- Options for autoapi -----------------------------------------------------

autoapi_dirs = [
    # "../../src/eq1lab",
    # "../../src/eq1lab_core",
    # "../../src/eq1lab_base",
    "../../src/eq1_pulse",
]
autoapi_template_dir = "_templates/autoapi"


autoapi_keep_files = _to_bool(os.environ.get("AUTOAPI_KEEP_FILES", False))

# Automatically extract typehints when specified and place them in
# descriptions of the relevant function/method.
autodoc_typehints = "description"


# Don't show class signature with the class' name.
# autodoc_class_signature = "separated"

autoapi_python_use_implicit_namespaces = True
autoapi_python_class_content = "both"
autoclass_content = "both"


def setup(sphinx):  # noqa: D103
    sphinx.connect("autoapi-skip-member", autoapi_skip_member)  #  type: ignore[name-defined]  # noqa: F405


# Default: 'module'
# This configuration value specifies the level at which objects are rendered on a single page. Valid levels, in descending order of hierarchy, are as follows:
# module: Packages, modules, subpackages, and submodules.
# class: Classes, exceptions, and all object types mentioned above.
# function: Functions, and all object types mentioned above.
# method: Methods, and all object types mentioned above.
# attribute: Class and module level attributes, properties, and all object types mentioned
autoapi_own_page_level = "module"


# Options for display of the generated documentation.
autoapi_options = [
    "members",  # Display children of an object
    "undoc-members",  # Display objects that have no docstring
    "show-inheritance",  # Display a list of base classes below the class signature.
    "show-module-summary",  # Whether to include autosummary directives in generated module documentation.
    # "private-members", #  Display private objects (eg. _foo in Python)
    "special-members",  # Display special objects (eg. __foo__ in Python)
    "imported-members",  # For objects imported into a package, display objects imported from the same top level package or module. This option does not effect objects imported into a module.
    # "show-module-summary", # Whether to include autosummary directives in generated module documentation.
]

if _to_bool(os.environ.get("AUTOAPI_PRIVATE_MEMBERS", False)):
    autoapi_options.append(
        "private-members"  # Display private objects (eg. _foo in Python)
    )

if _to_bool(os.environ.get("AUTOAPI_INHERITANCE_DIAGRAM", True)):
    autoapi_options.append(
        "show-inheritance-diagram"  #  Display an inheritance diagram in generated class documentation. It makes use of the sphinx.ext.inheritance_diagram extension, and requires Graphviz to be installed.
    )

if _to_bool(os.environ.get("AUTOAPI_INHERITED_MEMBERS", False)):
    autoapi_options.append(
        "inherited-members"  # Display children of an object that have been inherited from a base class.
    )

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

inheritance_graph_attrs = dict(rankdir="TB", size='""')
graphviz_output_format = "svg"

# To remove the index page altogether, turn off the autoapi_add_toctree_entry configuration option:
# autoapi_add_toctree_entry = False
# You will then need to include the generated documentation in the toctree yourself.
# For example if you were generating documentation for a package called “example”,
# you would add the following toctree entry:

# .. toctree::
#    autoapi/example/index
# Note that autoapi/ is the default location of documentation, as configured by autoapi_root. If you change autoapi_root, then the entry that you need to add would change also.

autoapi_add_toctree_entry = False


todo_include_todos = True
todo_emit_warnings = True
