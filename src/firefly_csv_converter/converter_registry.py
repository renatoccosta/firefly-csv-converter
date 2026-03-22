import argparse
import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass


ConverterHandler = Callable[[argparse.Namespace], None]


def normalize_token(value: str) -> str:
    return value.strip().casefold().replace("_", "-")


@dataclass(frozen=True)
class ConverterSpec:
    input_format: str
    output_format: str
    model: str
    handler: ConverterHandler
    description: str
    aliases: tuple[str, ...] = ()
    required_options: tuple[str, ...] = ()

    def matches(self, input_format: str, output_format: str, model: str) -> bool:
        if self.input_format != normalize_token(input_format):
            return False
        if self.output_format != normalize_token(output_format):
            return False

        accepted_models = {self.model, *self.aliases}
        return normalize_token(model) in accepted_models


class ConverterRegistry:
    def __init__(self) -> None:
        self._converters: list[ConverterSpec] = []
        self._loaded_modules: set[str] = set()

    def register(
        self,
        *,
        input_format: str,
        output_format: str,
        model: str,
        description: str,
        aliases: tuple[str, ...] = (),
        required_options: tuple[str, ...] = (),
    ) -> Callable[[ConverterHandler], ConverterHandler]:
        def decorator(handler: ConverterHandler) -> ConverterHandler:
            spec = ConverterSpec(
                input_format=normalize_token(input_format),
                output_format=normalize_token(output_format),
                model=normalize_token(model),
                handler=handler,
                description=description,
                aliases=tuple(normalize_token(alias) for alias in aliases),
                required_options=required_options,
            )
            self._converters.append(spec)
            return handler

        return decorator

    def all(self) -> tuple[ConverterSpec, ...]:
        return tuple(self._converters)

    def find(self, input_format: str, output_format: str, model: str) -> ConverterSpec | None:
        for spec in self._converters:
            if spec.matches(input_format, output_format, model):
                return spec
        return None

    def load_package_converters(self, package_name: str) -> None:
        package = importlib.import_module(package_name)

        for module_info in pkgutil.iter_modules(package.__path__):
            if not module_info.name.startswith("convert_"):
                continue

            module_name = f"{package_name}.{module_info.name}"
            if module_name in self._loaded_modules:
                continue

            module = importlib.import_module(module_name)
            register_converters = getattr(module, "register_converters", None)
            if callable(register_converters):
                register_converters(self)

            self._loaded_modules.add(module_name)


registry = ConverterRegistry()
