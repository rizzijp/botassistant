from app.semantic.loader import load_semantic_model

def debug():
    model = load_semantic_model()
    
    fact_table = next(t for t in model.tables if t.name == 'sales')
    product_table = next(t for t in model.tables if t.name == 'products')
    
    print(f"FACT: '{fact_table.name}' -> norm: '{fact_table.name.strip().lower()}'")
    print(f"DIM: '{product_table.name}' -> norm: '{product_table.name.strip().lower()}'")
    
    print("\nRELATIONSHIPS:")
    for r in model.relationships:
        r_from = (r.from_table or "").strip().lower()
        r_to = (r.to_table or "").strip().lower()
        print(f"  '{r.from_table}' -> '{r.to_table}' | Norm: '{r_from}' -> '{r_to}'")
        
        if r_from == 'sales' and r_to == 'products':
            print("  ✅ MATCH FOUND: sales -> products")

if __name__ == "__main__":
    debug()
