"""
In-memory Entity base class and registry.

Mirrors the ``ic_python_db.Entity`` API used by all GGG entities:
    Entity(**kwargs)          → create + auto-assign _id
    Entity["alias_value"]     → lookup by alias field
    Entity.load(id)           → lookup by _id
    Entity.instances()        → list all of this type
    Entity.count()            → count all of this type
    Entity.find(d)            → filter by field match
    Entity.load_some(from, n) → range load by _id
    Entity.max_id()           → highest _id assigned
    entity.delete()           → remove from registry
    entity.serialize()        → dict of public fields
"""

from datetime import datetime, timezone


class EntityRegistry:
    """Global in-memory store. One dict per entity class name."""

    def __init__(self):
        self._stores = {}      # {class_name: {_id_str: instance}}
        self._counters = {}    # {class_name: int}

    def reset(self):
        self._stores.clear()
        self._counters.clear()

    def next_id(self, cls_name):
        c = self._counters.get(cls_name, 0) + 1
        self._counters[cls_name] = c
        return c

    def store(self, entity):
        cls_name = type(entity).__name__
        bucket = self._stores.setdefault(cls_name, {})
        bucket[entity._id] = entity

    def get(self, cls_name, _id):
        return self._stores.get(cls_name, {}).get(str(_id))

    def get_all(self, cls_name):
        return list(self._stores.get(cls_name, {}).values())

    def remove(self, entity):
        cls_name = type(entity).__name__
        self._stores.get(cls_name, {}).pop(entity._id, None)


_registry = EntityRegistry()


class _EntityMeta(type):
    """Metaclass that provides Entity["alias_value"] bracket lookup."""

    def __getitem__(cls, alias_value):
        alias_field = getattr(cls, "__alias__", None)
        if alias_field is None:
            return None
        for inst in _registry.get_all(cls.__name__):
            if getattr(inst, alias_field, None) == alias_value:
                return inst
        return None


class MockEntity(metaclass=_EntityMeta):
    """Base class for all mock GGG entities."""

    __alias__ = None

    def __init__(self, **kwargs):
        cls_name = type(self).__name__
        self._id = str(_registry.next_id(cls_name))
        self._type = cls_name
        self._loaded = False
        now = datetime.now(timezone.utc).isoformat()
        self.timestamp_created = now
        self.timestamp_updated = now
        self.creator = "test-principal"
        self.updater = "test-principal"
        self.owner = "test-principal"
        for k, v in kwargs.items():
            setattr(self, k, v)
        _registry.store(self)

    @classmethod
    def load(cls, entity_id, level=0):
        return _registry.get(cls.__name__, str(entity_id))

    @classmethod
    def instances(cls):
        return list(_registry.get_all(cls.__name__))

    @classmethod
    def count(cls):
        return len(_registry.get_all(cls.__name__))

    @classmethod
    def max_id(cls):
        return _registry._counters.get(cls.__name__, 0)

    @classmethod
    def find(cls, d):
        results = []
        for inst in cls.instances():
            if all(getattr(inst, k, None) == v for k, v in d.items()):
                results.append(inst)
        return results

    @classmethod
    def load_some(cls, from_id, count=10):
        results = []
        for i in range(from_id, from_id + count):
            inst = cls.load(str(i))
            if inst is not None:
                results.append(inst)
        return results

    def delete(self):
        _registry.remove(self)

    def serialize(self):
        return {
            k: v for k, v in self.__dict__.items()
            if not k.startswith("_")
        }

    def __getattr__(self, name):
        """Return None for unset fields (matches ic_python_db behavior)."""
        if name.startswith("_"):
            raise AttributeError(name)
        return None

    def __repr__(self):
        alias = getattr(self, "__alias__", None)
        if alias:
            alias_val = getattr(self, alias, None)
            if alias_val is not None:
                return f"{self._type}({alias}={alias_val!r})"
        return f"{self._type}(_id={self._id!r})"
