import sys

from setuptools import Extension, setup
import pybind11


def _cpp_compile_args() -> list[str]:
    # ram_limiter_native.cpp uses std::optional and std::string_view, so it
    # requires C++17. MSVC uses /std:c++17, while GCC/Clang use -std=c++17.
    if sys.platform.startswith("win"):
        return ["/std:c++17", "/EHsc"]
    return ["-std=c++17"]


ext_modules = [
    Extension(
        "ram_limiter_native",
        sources=["ram_limiter_native.cpp"],
        include_dirs=[pybind11.get_include()],
        language="c++",
        extra_compile_args=_cpp_compile_args(),
    ),
]

setup(
    name="ram_limiter_native",
    version="1.0",
    ext_modules=ext_modules,
)
