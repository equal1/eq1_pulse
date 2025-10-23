When generating (Python) documentation:
- Use ReST and Sphinx format
    - replace `Args:` with the `:param:` directive (and so on)
    - replace `Yields:` with the `:yield:` directive
    - replace `Returns:` with the `:return:` directive
    - replace `Raises:` with the `:raises:` directive
    - etc.
- don't mention the data types of the params in the docstring (omit `:type:`)
- replace 'None' with ':obj:`None`'
- replace 'True' and 'False' with ':obj:`True`' and ':obj:`False`'
- add an empty line after sections like Examples, Notes, etc.
- code blocks should be indented by 4 spaces and preceded by the '.. code-block:: python' directive
    - the directive should not be indented
    - the directive should be preceded by an empty line and followed by an empty line

- use the `:func:` directive for function name references (e.g. :func:`function_name`)
- use the `:meth:` directive for method references (e.g. :meth:`method_name`)
- use the `:attr:` directive for attribute references (e.g. :attr:`attribute_name`)
- use the `:class:` directive for class references (e.g. :class:`ClassName`)
- use the `:obj:` directive for object references (e.g. :obj:`object_name`)
- inline fixed-width text should be enclosed in double backticks (e.g. ``fixed-width text``)
    - except for code blocks, which should be indented by 4 spaces

Misc:
- (UP038) Use `X | Y` in `isinstance` call instead of `(X, Y)`
