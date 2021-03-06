"""
Functions to generate methods and pin them to the appropriate classes.
"""
import operator

from pandas.core.dtypes.generic import ABCDataFrame, ABCSeries

from pandas.core.ops.roperator import (
    radd,
    rdivmod,
    rfloordiv,
    rmod,
    rmul,
    rpow,
    rsub,
    rtruediv,
)


def _get_method_wrappers(cls):
    """
    Find the appropriate operation-wrappers to use when defining flex/special
    arithmetic, boolean, and comparison operations with the given class.

    Parameters
    ----------
    cls : class

    Returns
    -------
    arith_flex : function or None
    comp_flex : function or None
    """
    # TODO: make these non-runtime imports once the relevant functions
    #  are no longer in __init__
    from pandas.core.ops import (
        flex_arith_method_FRAME,
        flex_comp_method_FRAME,
        flex_method_SERIES,
    )

    if issubclass(cls, ABCSeries):
        # Just Series
        arith_flex = flex_method_SERIES
        comp_flex = flex_method_SERIES
    elif issubclass(cls, ABCDataFrame):
        arith_flex = flex_arith_method_FRAME
        comp_flex = flex_comp_method_FRAME
    return arith_flex, comp_flex


def add_special_arithmetic_methods(cls):
    """
    Adds the full suite of special arithmetic methods (``__add__``,
    ``__sub__``, etc.) to the class.

    Parameters
    ----------
    cls : class
        special methods will be defined and pinned to this class
    """
    new_methods = {}

    def _wrap_inplace_method(method):
        """
        return an inplace wrapper for this method
        """

        def f(self, other):
            result = method(self, other)
            # Delete cacher
            self._reset_cacher()
            # this makes sure that we are aligned like the input
            # we are updating inplace so we want to ignore is_copy
            self._update_inplace(
                result.reindex_like(self, copy=False), verify_is_copy=False
            )

            return self

        name = method.__name__.strip("__")
        f.__name__ = f"__i{name}__"
        return f

    # wrap methods that we get from OpsMixin
    new_methods.update(
        dict(
            __iadd__=_wrap_inplace_method(cls.__add__),
            __isub__=_wrap_inplace_method(cls.__sub__),
            __imul__=_wrap_inplace_method(cls.__mul__),
            __itruediv__=_wrap_inplace_method(cls.__truediv__),
            __ifloordiv__=_wrap_inplace_method(cls.__floordiv__),
            __imod__=_wrap_inplace_method(cls.__mod__),
            __ipow__=_wrap_inplace_method(cls.__pow__),
        )
    )
    new_methods.update(
        dict(
            __iand__=_wrap_inplace_method(cls.__and__),
            __ior__=_wrap_inplace_method(cls.__or__),
            __ixor__=_wrap_inplace_method(cls.__xor__),
        )
    )

    _add_methods(cls, new_methods=new_methods)


def add_flex_arithmetic_methods(cls):
    """
    Adds the full suite of flex arithmetic methods (``pow``, ``mul``, ``add``)
    to the class.

    Parameters
    ----------
    cls : class
        flex methods will be defined and pinned to this class
    """
    flex_arith_method, flex_comp_method = _get_method_wrappers(cls)
    new_methods = _create_methods(cls, flex_arith_method, flex_comp_method)
    new_methods.update(
        dict(
            multiply=new_methods["mul"],
            subtract=new_methods["sub"],
            divide=new_methods["div"],
        )
    )
    # opt out of bool flex methods for now
    assert not any(kname in new_methods for kname in ("ror_", "rxor", "rand_"))

    _add_methods(cls, new_methods=new_methods)


def _create_methods(cls, arith_method, comp_method):
    # creates actual flex methods based upon arithmetic, and comp method
    # constructors.

    have_divmod = issubclass(cls, ABCSeries)
    # divmod is available for Series

    new_methods = {}

    new_methods.update(
        dict(
            add=arith_method(operator.add),
            radd=arith_method(radd),
            sub=arith_method(operator.sub),
            mul=arith_method(operator.mul),
            truediv=arith_method(operator.truediv),
            floordiv=arith_method(operator.floordiv),
            mod=arith_method(operator.mod),
            pow=arith_method(operator.pow),
            rmul=arith_method(rmul),
            rsub=arith_method(rsub),
            rtruediv=arith_method(rtruediv),
            rfloordiv=arith_method(rfloordiv),
            rpow=arith_method(rpow),
            rmod=arith_method(rmod),
        )
    )
    new_methods["div"] = new_methods["truediv"]
    new_methods["rdiv"] = new_methods["rtruediv"]
    if have_divmod:
        # divmod doesn't have an op that is supported by numexpr
        new_methods["divmod"] = arith_method(divmod)
        new_methods["rdivmod"] = arith_method(rdivmod)

    new_methods.update(
        dict(
            eq=comp_method(operator.eq),
            ne=comp_method(operator.ne),
            lt=comp_method(operator.lt),
            gt=comp_method(operator.gt),
            le=comp_method(operator.le),
            ge=comp_method(operator.ge),
        )
    )

    new_methods = {k.strip("_"): v for k, v in new_methods.items()}
    return new_methods


def _add_methods(cls, new_methods):
    for name, method in new_methods.items():
        setattr(cls, name, method)
