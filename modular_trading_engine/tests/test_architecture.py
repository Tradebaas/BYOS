from pytest_archon import archrule

def test_layer1_boundaries():
    """
    Layer 1 (Data) is purely mathematical and cannot depend on any higher layer concepts.
    """
    (
        archrule("layer1_should_not_import_higher_layers")
        .match("src.layer1_data*")
        .should_not_import("src.layer2_theory*")
        .should_not_import("src.layer3_strategy*")
        .should_not_import("src.layer4_execution*")
        .check("src")
    )

def test_layer2_boundaries():
    """
    Layer 2 (Theory) identifies base structures based on L1 Data.
    It cannot know about strategy configurations or broker execution.
    """
    (
        archrule("layer2_should_not_import_higher_layers")
        .match("src.layer2_theory*")
        .should_not_import("src.layer3_strategy*")
        .should_not_import("src.layer4_execution*")
        .check("src")
    )

def test_layer3_boundaries():
    """
    Layer 3 (Strategy) processes L2 events via modular rules.
    It resolves to Order Intents, but cannot import the L4 execution API itself.
    """
    (
        archrule("layer3_should_not_import_execution")
        .match("src.layer3_strategy*")
        .should_not_import("src.layer4_execution*")
        .check("src")
    )
