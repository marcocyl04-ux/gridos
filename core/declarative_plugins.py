"""
Declarative Plugin System — YAML-based plugins for formulas, agents, templates.

This provides a secure, auditable alternative to Python plugins.
No executable code = no security concerns.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml


@dataclass
class FormulaSpec:
    """A formula defined in YAML."""
    name: str  # The formula name (e.g., "BLACK_SCHOLES")
    inputs: List[Dict[str, Any]]  # List of {name, type, desc, optional}
    output: Dict[str, str]  # {type: ...}
    expression: str  # The formula expression
    where: Dict[str, str] = field(default_factory=dict)  # Helper definitions
    category: str = "custom"  # For grouping in the UI
    description: str = ""
    examples: List[str] = field(default_factory=list)


@dataclass
class AgentSpec:
    """An agent defined in YAML."""
    id: str
    display_name: str
    description: str = ""
    system_prompt: str = ""
    router_description: str = ""
    category: str = "custom"
    triggers: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TemplateSpec:
    """A template defined in YAML."""
    id: str
    name: str
    description: str = ""
    category: str = "custom"
    cells: Dict[str, Any] = field(default_factory=dict)  # A1 -> {value, formula}
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginManifest:
    """A declarative plugin manifest."""
    slug: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    category: str = "custom"
    formulas: List[FormulaSpec] = field(default_factory=list)
    agents: List[AgentSpec] = field(default_factory=list)
    templates: List[TemplateSpec] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Other plugin slugs


class DeclarativePluginLoader:
    """Load and manage declarative (YAML) plugins."""
    
    def __init__(self, plugins_dir: Path = Path("plugins")):
        self.plugins_dir = plugins_dir
        self.registry: Dict[str, PluginManifest] = {}
        self.formula_registry: Dict[str, FormulaSpec] = {}
        self.agent_registry: Dict[str, AgentSpec] = {}
        self.template_registry: Dict[str, TemplateSpec] = {}
    
    def load_all(self) -> List[PluginManifest]:
        """Load all declarative plugins from the plugins directory."""
        manifests = []
        
        if not self.plugins_dir.exists():
            return manifests
        
        for entry in sorted(self.plugins_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith((".", "_")):
                continue
            
            manifest_path = entry / "plugin.yaml"
            if not manifest_path.exists():
                continue
            
            try:
                manifest = self._load_manifest(manifest_path, entry.name)
                if manifest:
                    manifests.append(manifest)
                    self._register_manifest(manifest)
            except Exception as e:
                print(f"[declarative_plugins] Failed to load {entry.name}: {e}")
        
        return manifests
    
    def _load_manifest(self, path: Path, slug: str) -> Optional[PluginManifest]:
        """Load a single plugin manifest from YAML."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        if not data:
            return None
        
        # Parse formulas - handles both dict and list YAML formats
        raw_formulas = data.get("formulas", {})
        formulas = []
        if isinstance(raw_formulas, dict):
            # Dict format: {"=FORMULA_NAME": {inputs: [...], ...}}
            for formula_key, f_data in raw_formulas.items():
                clean_name = formula_key.lstrip("=")
                formulas.append(FormulaSpec(
                    name=clean_name.upper(),
                    inputs=f_data.get("inputs", []),
                    output=f_data.get("output", {"type": "number"}),
                    expression=f_data.get("expression", ""),
                    where=f_data.get("where", {}),
                    category=f_data.get("category", "custom"),
                    description=f_data.get("description", ""),
                    examples=f_data.get("examples", [])
                ))
        elif isinstance(raw_formulas, list):
            # List format: [{name: "FORMULA_NAME", ...}, ...]
            for f_data in raw_formulas:
                formulas.append(FormulaSpec(
                    name=f_data["name"].upper(),
                    inputs=f_data.get("inputs", []),
                    output=f_data.get("output", {"type": "number"}),
                    expression=f_data.get("expression", ""),
                    where=f_data.get("where", {}),
                    category=f_data.get("category", "custom"),
                    description=f_data.get("description", ""),
                    examples=f_data.get("examples", [])
                ))
        
        # Parse agents
        agents = []
        for a_data in data.get("agents", []):
            agents.append(AgentSpec(
                id=a_data["id"],
                display_name=a_data.get("display_name", a_data["id"]),
                description=a_data.get("description", ""),
                system_prompt=a_data.get("system_prompt", ""),
                router_description=a_data.get("router_description", ""),
                category=a_data.get("category", "custom"),
                triggers=a_data.get("triggers", [])
            ))
        
        # Parse templates
        templates = []
        for t_data in data.get("templates", []):
            templates.append(TemplateSpec(
                id=t_data["id"],
                name=t_data.get("name", t_data["id"]),
                description=t_data.get("description", ""),
                category=t_data.get("category", "custom"),
                cells=t_data.get("cells", {}),
                metadata=t_data.get("metadata", {})
            ))
        
        return PluginManifest(
            slug=slug,
            name=data.get("name", slug),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            category=data.get("category", "custom"),
            formulas=formulas,
            agents=agents,
            templates=templates,
            dependencies=data.get("dependencies", [])
        )
    
    def _register_manifest(self, manifest: PluginManifest) -> None:
        """Register a manifest's contents into the registries."""
        self.registry[manifest.slug] = manifest
        
        for formula in manifest.formulas:
            self.formula_registry[formula.name] = formula
        
        for agent in manifest.agents:
            self.agent_registry[agent.id] = agent
        
        for template in manifest.templates:
            self.template_registry[template.id] = template
    
    def get_formula(self, name: str) -> Optional[FormulaSpec]:
        """Get a formula by name."""
        return self.formula_registry.get(name.upper())
    
    def get_agent(self, agent_id: str) -> Optional[AgentSpec]:
        """Get an agent by ID."""
        return self.agent_registry.get(agent_id)
    
    def get_template(self, template_id: str) -> Optional[TemplateSpec]:
        """Get a template by ID."""
        return self.template_registry.get(template_id)
    
    def list_formulas(self, category: Optional[str] = None) -> List[FormulaSpec]:
        """List all formulas, optionally filtered by category."""
        formulas = list(self.formula_registry.values())
        if category:
            formulas = [f for f in formulas if f.category == category]
        return formulas
    
    def list_agents(self) -> List[AgentSpec]:
        """List all agents."""
        return list(self.agent_registry.values())
    
    def list_templates(self, category: Optional[str] = None) -> List[TemplateSpec]:
        """List all templates, optionally filtered by category."""
        templates = list(self.template_registry.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates


class ExpressionEvaluator:
    """Evaluate declarative formula expressions.
    
    Formulas are defined as expressions like:
        "S * norm_cdf(d1) - K * exp(-r*T) * norm_cdf(d2)"
    With helper definitions in `where`:
        d1: "(ln(S/K) + (r + sigma^2/2)*T) / (sigma * sqrt(T))"
        d2: "d1 - sigma * sqrt(T)"
    """
    
    def __init__(self, math_registry: Dict[str, Callable]):
        self.math_registry = math_registry
    
    def evaluate(self, spec: FormulaSpec, **inputs) -> Any:
        """Evaluate a formula with given inputs."""
        import math
        
        # Build evaluation context with math functions and module access
        context = {
            "math": math,  # Allow math.log, math.sqrt, etc.
            "ln": math.log,
            "exp": math.exp,
            "sqrt": math.sqrt,
            "abs": abs,
            "min": min,
            "max": max,
            "pow": pow,
            "log": math.log,  # alias
        }
        
        # Add math functions from registry
        context.update(self.math_registry)
        
        # Add inputs
        context.update(inputs)
        
        # Evaluate helper expressions (from `where`)
        for name, expr in spec.where.items():
            try:
                context[name] = eval(expr, {"__builtins__": {}}, context)
            except Exception as e:
                raise ValueError(f"Error evaluating '{name}' = '{expr}': {e}")
        
        # Evaluate main expression
        try:
            result = eval(spec.expression, {"__builtins__": {}}, context)
            return result
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{spec.expression}': {e}")


# Default math functions available in declarative formulas
DEFAULT_MATH_REGISTRY: Dict[str, Callable] = {
    "norm_cdf": lambda x: 0.5 * (1 + __import__("math").erf(x / (2 ** 0.5))),
    "norm_pdf": lambda x: (1 / ((2 * __import__("math").pi) ** 0.5)) * __import__("math").exp(-0.5 * x * x),
}


def install_declarative_formulas(loader: DeclarativePluginLoader, kernel: Any) -> None:
    """Install declarative formulas into the kernel's formula registry."""
    import math
    from core.functions import _REGISTRY as FORMULA_REGISTRY
    
    evaluator = ExpressionEvaluator(DEFAULT_MATH_REGISTRY)
    
    for name, spec in loader.formula_registry.items():
        # Capture spec in closure properly using a factory function
        def _make_formula_fn(s):
            def formula_fn(*args):
                # Map positional args to named inputs
                inputs = {}
                for i, inp_def in enumerate(s.inputs):
                    inp_name = inp_def["name"] if isinstance(inp_def, dict) else inp_def
                    if i < len(args):
                        inputs[inp_name] = args[i]
                    elif isinstance(inp_def, dict) and "default" in inp_def:
                        inputs[inp_name] = inp_def["default"]
                return evaluator.evaluate(s, **inputs)
            formula_fn.__name__ = s.name.lower()
            return formula_fn
        
        fn = _make_formula_fn(spec)
        FORMULA_REGISTRY[name.upper()] = fn
        # Also register into kernel's evaluator if it has one
        if hasattr(kernel, "evaluator") and hasattr(kernel.evaluator, "register_custom"):
            kernel.evaluator.register_custom(name.upper(), fn)
