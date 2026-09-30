//! Fail-closed checks of the T2_CONT_FILE loader (single table and manifest).
//!   cargo run --release -p solver --features t2-cont --example t2_cont_loader_check
use solver::preflop::t2cont::parse_file;

    fn table(node: usize, live: u32, seats: &[usize], n: usize, bad: bool) -> serde_json::Value {
        let mut vals: Vec<serde_json::Value> = (0..n).map(|i| serde_json::json!(1.0 + i as f64 * 0.01)).collect();
        if bad {
            vals[5] = serde_json::json!("NaN");
        }
        serde_json::json!({"schema": "t2_hu_continuation_table_v1", "value_convention": "gross_share", "node": node,
            "live": live, "pot_bb": 5.5, "seats": seats.iter().map(|s| serde_json::json!({"seat": s, "gross": vals.clone()})).collect::<Vec<_>>()})
    }

    fn write(dir: &std::path::Path, name: &str, v: &serde_json::Value) -> String {
        let p = dir.join(name);
        std::fs::write(&p, serde_json::to_vec(v).unwrap()).unwrap();
        p.to_string_lossy().into_owned()
    }

fn main() {
        let dir = std::env::temp_dir().join(format!("t2cont_loader_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let a = write(&dir, "a.json", &table(28, 0b1010, &[1, 3], 169, false));
        let b = write(&dir, "b.json", &table(6, 0b1100, &[2, 3], 169, false));
        let t = parse_file(&a).unwrap();
        assert_eq!(t.by_node.len(), 1);
        let m = write(&dir, "m.json", &serde_json::json!({"schema": "t2_hu_continuation_manifest_v1", "tables": [{"file": "a.json"}, {"file": "b.json"}]}));
        let t = parse_file(&m).unwrap();
        assert_eq!(t.by_node.keys().copied().collect::<Vec<_>>(), vec![6, 28]);
        let _ = b;
        // duplicate node
        write(&dir, "c.json", &table(28, 0b1010, &[1, 3], 169, false));
        let m = write(&dir, "dup.json", &serde_json::json!({"schema": "t2_hu_continuation_manifest_v1", "tables": [{"file": "a.json"}, {"file": "c.json"}]}));
        assert!(parse_file(&m).err().unwrap().contains("duplicate node 28"));
        // wrong schema / convention
        let mut v = table(28, 0b1010, &[1, 3], 169, false);
        v["schema"] = serde_json::json!("x");
        assert!(parse_file(&write(&dir, "s.json", &v)).is_err());
        let mut v = table(28, 0b1010, &[1, 3], 169, false);
        v["value_convention"] = serde_json::json!("net_chip_delta");
        assert!(parse_file(&write(&dir, "v.json", &v)).err().unwrap().contains("gross_share"));
        // 168 values, non-numeric value, seat outside the live mask, missing live seat
        assert!(parse_file(&write(&dir, "n.json", &table(28, 0b1010, &[1, 3], 168, false))).err().unwrap().contains("not 169"));
        assert!(parse_file(&write(&dir, "f.json", &table(28, 0b1010, &[1, 3], 169, true))).err().unwrap().contains("non-finite"));
        assert!(parse_file(&write(&dir, "l.json", &table(28, 0b1010, &[0, 3], 169, false))).err().unwrap().contains("not in live mask"));
        assert!(parse_file(&write(&dir, "m1.json", &table(28, 0b1010, &[3], 169, false))).err().unwrap().contains("1 seats"));
        // empty manifest
        assert!(parse_file(&write(&dir, "e.json", &serde_json::json!({"schema": "t2_hu_continuation_manifest_v1", "tables": []}))).is_err());
        std::fs::remove_dir_all(&dir).ok();
    println!("loader checks passed: single, manifest, duplicate node, schema, convention, 168 values, non-numeric, seat outside live, missing live seat, empty manifest");
}
