from timefred.dikt import DiktField


# TODO:
#  - arbitrary attrs

class DictSubclass(dict):
    pass


def test__get__setitem_in_instance():
    """Tests that dikt['foo'] has the computed value after getting attribute"""

    class HasDiktField(DictSubclass):
        foo = DiktField(default_factory=lambda x: x + 1)
        bar = DiktField(int)
        baz = DiktField()

        def __init__(self, foo) -> None:
            super().__init__()
            self.foo = foo

    # TODO: turn everything to Field on __setattr__
    has_diktfield = HasDiktField(5)
    assert has_diktfield.foo == 6
    assert has_diktfield['foo'] == 6
    assert has_diktfield.foo == 6

    has_diktfield.foo = 10
    assert has_diktfield.foo == 11
    assert has_diktfield['foo'] == 11

    has_diktfield.bar = '5'
    assert has_diktfield.bar == 5
    assert has_diktfield['bar'] == 5


def test__get__getitem_in_instance():
    class HasDiktField(DictSubclass):
        foo = DiktField()

    has_diktfield = HasDiktField()
    has_diktfield['foo'] = 'bar'
    assert has_diktfield.foo == 'bar'
    assert has_diktfield['foo'] == 'bar'

    class DoesntSupportGetitem:
        foo = DiktField()

    doesnt_support_getitem = DoesntSupportGetitem()
    doesnt_support_getitem.foo = 'bar'
    assert doesnt_support_getitem.foo == 'bar'
    assert doesnt_support_getitem['foo'] == 'bar'