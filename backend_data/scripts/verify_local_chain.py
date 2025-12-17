from app.semantic.router import generate_query_plan
from app.semantic.compiler import compile_sql
import json

def test_local_chain():
    print("🚀 TESTING LOCAL CHAIN (Router -> Compiler)")
    
    query = "Ventas de monitores"
    print(f"\nQUERY: '{query}'")
    
    # 1. Router
    try:
        plan = generate_query_plan(query)
        print(f"\n✅ PLAN GENERATED: {plan.model_dump_json()}")
    except Exception as e:
        print(f"\n❌ ROUTER FAILED: {e}")
        return

    # 2. Compiler
    try:
        sql = compile_sql(plan)
        print("\n✅ SQL COMPILED:")
        print(sql)
    except Exception as e:
        print(f"\n❌ COMPILER FAILED: {e}")
        return

    if "JOIN" in sql:
        print("\n🎉 SUCCESS! JOIN detected in SQL.")
    else:
        print("\n⚠️ WARNING: No JOIN detected (might be wrong if 'monitores' is in products table).")

if __name__ == "__main__":
    test_local_chain()
