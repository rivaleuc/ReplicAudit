import sys, os, types, importlib.util
import pytest


def _install_fake_genlayer():
    m = types.ModuleType("genlayer")

    class u256(int):
        pass

    class Address(str):
        pass

    class TreeMap:
        def __class_getitem__(cls, item):
            return cls
        def __init__(self):
            self._d = {}
        def __getitem__(self, k):
            return self._d[k]
        def __setitem__(self, k, v):
            self._d[k] = v
        def __contains__(self, k):
            return k in self._d

    class _ContractBase:
        def __new__(cls, *a, **k):
            self = super().__new__(cls)
            anns = {}
            for klass in reversed(cls.__mro__):
                anns.update(getattr(klass, "__annotations__", {}))
            for name, typ in anns.items():
                if typ is TreeMap:
                    setattr(self, name, TreeMap())
            return self

    def _pass(fn):
        return fn

    class _Write:
        def __call__(self, fn):
            return fn
        payable = staticmethod(_pass)

    class _public:
        write = _Write()
        view = staticmethod(_pass)

    class _message:
        sender_address = "0xa000000000000000000000000000000000000001"
        value = 0

    class _nondet:
        @staticmethod
        def exec_prompt(*a, **k):
            return {}

    class _eq:
        @staticmethod
        def prompt_comparative(fn, principle=""):
            return fn()

    class _gl:
        Contract = _ContractBase
        public = _public
        message = _message
        nondet = _nondet
        eq_principle = _eq

    m.gl = _gl
    m.u256 = u256
    m.Address = Address
    m.TreeMap = TreeMap
    sys.modules["genlayer"] = m


_install_fake_genlayer()
_HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT_PATH = os.path.normpath(os.path.join(_HERE, "..", "contracts", "replic_audit.py"))


def load_contract():
    spec = importlib.util.spec_from_file_location("ra_under_test", CONTRACT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def contract():
    return load_contract()
