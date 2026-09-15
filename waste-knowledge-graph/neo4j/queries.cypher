// 在 Neo4j Browser 中执行，节点按 kind 字段区分 ITEM CATEGORY METHOD。
MATCH p=(a:WasteKGEntity {project:'wastekg_course'})-[:BELONGS_TO]->(b)
RETURN p LIMIT 150;

// 指定物品的类别与投放要求。
MATCH p=(a:WasteKGEntity {name:'香蕉皮', project:'wastekg_course'})-[r]->(b)
RETURN p;

// 四分类规模。
MATCH (a:WasteKGEntity {project:'wastekg_course'})-[:BELONGS_TO]->(c)
RETURN c.name AS category,count(a) AS items ORDER BY items DESC;

// 数据溯源。
MATCH (a:WasteKGEntity {name:'矿泉水瓶',project:'wastekg_course'})-[r]->(b)
RETURN a.name,r.evidence,r.source_url,r.provenance,r.review_status,b.name;

MATCH p=(a:WasteKGEntity {project:'wastekg_course'})-[r:BELONGS_TO]->(b)
WHERE r.review_status='source_labeled'
RETURN p LIMIT 100;

MATCH (a:WasteKGEntity {project:'wastekg_course'})-[r:BELONGS_TO]->(b)
RETURN r.review_status AS review_status,count(r) AS relations;
