from app.semantic.models.query_plan import QueryPlan, Filter
from app.semantic.compiler import compile_sql
from app.semantic.loader import load_semantic_model
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_compiler():
    print("STARTING COMPILER REPRODUCTION TEST")
    
    # 1. Load Model
    try:
        model = load_semantic_model()
        print(f"Model loaded. Found {len(model.tables)} tables and {len(model.relationships)} relationships.")
        
        print("\nDEFINED RELATIONSHIPS:")
        for r in model.relationships:
            print(f"   {r.from_table}.{r.from_column} -> {r.to_table}.{r.to_column}")
            
    except Exception as e:
        print(f"Failed to load model: {e}")
        return

    # 2. Define a Test Plan (that simulates 'Ventas de monitores')
    # Use metrics from 'sales' and filter on 'products'
    # This requires a JOIN from sales -> products
    plan = QueryPlan(
        metrics=["total_sales"],
        dimensions=["category"],
        filters=[
            Filter(column="product_name", operator="ILIKE", value="Monitor")
        ],
        limit=10,
        viz_type="bar"
    )
    
    print("\nTEST PLAN:")
    print(plan.model_dump_json(indent=2))
    
    # 3. Compile SQL
    try:
        sql = compile_sql(plan)
        print("\nGENERATED SQL:")
        print(sql)
        
        if "JOIN" not in sql:
            print("\nFAIL: JOIN clause missing in generated SQL!")
        else:
            print("\nSUCCESS: JOIN clause present.")
            
    except Exception as e:
        print(f"\nCOMPILATION ERROR: {e}")

if __name__ == "__main__":
    test_compiler()
