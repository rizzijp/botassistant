from app.semantic.models.query_plan import QueryPlan, Filter
from app.semantic.compiler import compile_sql
from app.semantic.loader import load_semantic_model

def test_optimization_bug():
    print("TESTING COMPILER OPTIMIZATION LOGIC")
    
    # 1. Load Model
    model = load_semantic_model()
    
    # 2. Define Plan: Valid metric (sales) but all dims/filters in 'products'
    # Query: "Ventas de monitores" -> Metric: total_sales (sales table), Filter: Monitor (products table)
    plan = QueryPlan(
        metrics=["total_sales"],
        dimensions=[], 
        filters=[Filter(column="product_name", operator="ILIKE", value="Monitor")],
        limit=5
    )
    
    print(f"Plan Metrics: {plan.metrics}")
    
    # 3. Compile
    sql = compile_sql(plan)
    print("\nGENERATED SQL:")
    print(sql)
    
    # 4. Check results
    if "JOIN" not in sql and "FROM sales" not in sql:
        print("\n❌ FAILURE: SQL queries 'products' directly but asks for 'total_sales' metric!")
        print("   This will cause: column 'total_sales' does not exist error.")
    elif "products" in sql and "sales" in sql and "JOIN" in sql:
        print("\n✅ SUCCESS: Compiler correctly joined 'sales' and 'products'.")
    else:
        print("\n⚠️ UNKNOWN STATE.")

if __name__ == "__main__":
    test_optimization_bug()
