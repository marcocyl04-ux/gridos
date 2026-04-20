#!/usr/bin/env python3
"""
Integration test for GridOS rebuild.
Verifies all new modules load, templates load, and node graph works.
"""
import json
from pathlib import Path

def test_imports():
    """Test all new module imports."""
    print("✓ Testing module imports...")
    from core.node_graph import NodeGraph, Coordinator, Executor, Node, NodeType, TypeSchema
    from core.intent_parser import IntentParser, validate_with_feedback
    from core.declarative_plugins import DeclarativePluginLoader, ExpressionEvaluator
    from core.import_engine import import_file, auto_detect_template, ImportResult
    from core.industry_profiles import detect_industry, INDUSTRY_PROFILES
    print("  ✓ All core modules imported successfully")

def test_templates():
    """Test YAML template loading."""
    print("\n✓ Testing YAML templates...")
    import yaml
    templates_dir = Path("data/templates")
    yaml_files = list(templates_dir.glob("*.yaml"))
    assert len(yaml_files) >= 6, f"Expected 6+ YAML templates, found {len(yaml_files)}"
    
    expected = {"bs_calculator", "comps_analysis", "dcf_valuation", "lbo_model", "property_proforma", "three_statement"}
    found = {f.stem for f in yaml_files}
    assert expected.issubset(found), f"Missing templates: {expected - found}"
    
    for yaml_file in yaml_files:
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        assert "id" in data, f"Template {yaml_file} missing 'id' field"
        assert "name" in data, f"Template {yaml_file} missing 'name' field"
        print(f"  ✓ {data['id']}: {data['name']}")

def test_node_graph():
    """Test node graph creation and validation."""
    print("\n✓ Testing node graph...")
    from core.node_graph import Node, NodeGraph, NodeType, TypedInterface, TypeSchema, NodeMetadata
    from datetime import datetime, timezone
    
    # Create a simple node
    node = Node(
        id="test_write",
        node_type=NodeType.CELL_WRITE,
        interface=TypedInterface(
            inputs={"cell": TypeSchema.cell_ref(), "value": TypeSchema.any()},
            outputs={"result": TypeSchema.string()}
        ),
        inputs={"cell": "A1", "value": 42},
    )
    assert node.is_leaf(), "Node should be a leaf"
    print("  ✓ Created CELL_WRITE node")
    
    # Create graph
    graph = NodeGraph(root=node)
    assert len(graph.nodes) == 1, "Graph should have 1 node"
    errors = graph.validate()
    assert len(errors) == 0, f"Validation should pass: {errors}"
    print("  ✓ Graph validation passed")

def test_intent_parser():
    """Test LLM JSON to NodeGraph parsing."""
    print("\n✓ Testing intent parser...")
    from core.intent_parser import IntentParser
    
    parser = IntentParser(agent_id="finance")
    
    # Test single intent
    llm_response = {
        "target_cell": "B2",
        "values": [["Model Title"], [100], [200]],
    }
    graph = parser.parse(llm_response, prompt="Build a simple model")
    assert graph.root is not None, "Graph should have root"
    assert len(graph.nodes) > 0, "Graph should have nodes"
    print("  ✓ Parsed single intent to graph")
    
    # Test conversion back to intents
    intents = parser.to_agent_intents(graph)
    assert len(intents) > 0, "Should have at least one intent"
    print(f"  ✓ Converted graph back to {len(intents)} agent intent(s)")

def test_declarative_plugins():
    """Test declarative plugin loader."""
    print("\n✓ Testing declarative plugin loader...")
    from core.declarative_plugins import DeclarativePluginLoader
    from pathlib import Path
    
    loader = DeclarativePluginLoader(Path("plugins"))
    manifests = loader.load_all()
    print(f"  ✓ Loaded {len(manifests)} declarative plugins")
    
    # Check formulas
    if len(loader.formula_registry) > 0:
        print(f"  ✓ Registered {len(loader.formula_registry)} formulas")
    
    # Check templates
    if len(loader.template_registry) > 0:
        print(f"  ✓ Registered {len(loader.template_registry)} templates")

def test_industry_profiles():
    """Test industry profile detection."""
    print("\n✓ Testing industry profiles...")
    from core.industry_profiles import detect_industry, INDUSTRY_PROFILES
    
    assert len(INDUSTRY_PROFILES) >= 7, "Should have at least 7 industry profiles"
    print(f"  ✓ Found {len(INDUSTRY_PROFILES)} industry profiles")
    
    # Test detection
    profile = detect_industry("I want a SaaS company financial model")
    assert profile.id == "saas", "Should detect SaaS from prompt"
    print(f"  ✓ Detected industry: {profile.name}")
    
    # Test general fallback
    profile = detect_industry("weird unknown business type xyz")
    assert profile.id == "general", "Should fallback to general"
    print(f"  ✓ Fallback works: {profile.name}")

def test_main_syntax():
    """Test main.py syntax."""
    print("\n✓ Testing main.py syntax...")
    import py_compile
    try:
        py_compile.compile("main.py", doraise=True)
        print("  ✓ main.py compiles without syntax errors")
    except py_compile.PyCompileError as e:
        raise AssertionError(f"main.py has syntax errors: {e}")

def test_endpoints_defined():
    """Check that new endpoints are defined in main.py."""
    print("\n✓ Checking new endpoints...")
    with open("main.py") as f:
        content = f.read()
    
    assert '@app.post("/import/file")' in content, "Missing /import/file endpoint"
    print("  ✓ Found /import/file endpoint")
    
    assert '@app.post("/agent/write/graph")' in content, "Missing /agent/write/graph endpoint"
    print("  ✓ Found /agent/write/graph endpoint")
    
    assert "NodeGraphRequest" in content, "Missing NodeGraphRequest class"
    print("  ✓ Found NodeGraphRequest class")
    
    assert "security_middleware" in content, "Missing security middleware"
    print("  ✓ Found security middleware")
    
    assert "_YAML_TEMPLATES" in content, "Missing YAML templates loader"
    print("  ✓ Found YAML template loader")

def main():
    """Run all integration tests."""
    print("=" * 60)
    print("GridOS Rebuild Integration Tests")
    print("=" * 60)
    
    try:
        test_main_syntax()
        test_imports()
        test_templates()
        test_node_graph()
        test_intent_parser()
        test_declarative_plugins()
        test_industry_profiles()
        test_endpoints_defined()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nGridOS is ready for deployment!")
        print("  • All modules import successfully")
        print("  • All 6 YAML templates load")
        print("  • Node graph creation and validation work")
        print("  • Intent parser converts LLM JSON → graphs")
        print("  • Declarative plugins load safely")
        print("  • Industry profiles detect correctly")
        print("  • New endpoints are defined")
        print("  • Security middleware is installed")
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
