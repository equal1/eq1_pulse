# ruff: noqa: E501
autodoc_type_aliases: dict[str, str] = {
    # Does not work as expected
    # "ConfigValue": "eq1x.framework.sweep.typedefs.ConfigValue",
    # "eq1x.yaml.ConfigNode": "eq1x.yaml.config_node.ConfigNode",
    # "ParameterInputLists": "collections.abc.Sequence[tuple[Parameter, list | numpy.ndarray]]",
    # "ParameterResultLists": "collections.abc.MutableMapping[qcodes.parameters.Parameter, list | numpy.ndarray | None]",
}
