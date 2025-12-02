from interactem.core.models.spec import (
    OperatorSpecParameter,
    OperatorSpecParameterBoolean,
    OperatorSpecParameterInteger,
    OperatorSpecParameterStrEnum,
    ParameterSpecType,
)


def test_integer_coerce_from_string():
    d = {
        "name": "width",
        "label": "Width",
        "description": "Width of image",
        "type": ParameterSpecType.INTEGER,
        "default": "100",
        "required": True,
    }

    p = OperatorSpecParameter.model_validate(d)
    assert p.root.type == "int"
    assert isinstance(p.root, OperatorSpecParameterInteger)
    assert isinstance(p.root.default, int) and p.root.default == 100


def test_str_enum_validation():
    good = {
        "name": "mode",
        "label": "Mode",
        "description": "Mode",
        "type": ParameterSpecType.STR_ENUM,
        "default": "auto",
        "options": ["auto", "manual"],
        "required": True,
    }
    p = OperatorSpecParameter.model_validate(good)
    assert p.root.type == "str-enum"
    assert isinstance(p.root, OperatorSpecParameterStrEnum)
    assert p.root.default == "auto"
    assert p.root.options == ["auto", "manual"]


def test_bool_coerce_from_string():
    d = {
        "name": "enabled",
        "label": "Enabled",
        "description": "Whether enabled",
        "type": ParameterSpecType.BOOLEAN,
        "default": "True",
        "required": False,
    }

    p = OperatorSpecParameter.model_validate(d)
    assert p.root.type == "bool"
    assert isinstance(p.root, OperatorSpecParameterBoolean)
    assert isinstance(p.root.default, bool) and p.root.default is True

    d2 = dict(d)
    d2["default"] = "false"
    p2 = OperatorSpecParameter.model_validate(d2)
    assert p2.root.default is False

    d3 = dict(d)
    d3["default"] = "0"
    p3 = OperatorSpecParameter.model_validate(d3)
    assert p3.root.default is False
