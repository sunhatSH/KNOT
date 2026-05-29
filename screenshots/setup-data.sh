#!/usr/bin/env bash
set -euo pipefail

API="http://localhost:8000/api/v1"

echo "==> Create workflows (global)"
curl -s -X POST "$API/workflows" \
  -H "Content-Type: application/json" \
  -d '{"name":"数据分析流水线","nodes":[{"id":"n1","type":"input","label":"输入"},{"id":"n2","type":"task","label":"数据采集","config":{"agent_role":"researcher"}},{"id":"n3","type":"task","label":"分析报告","config":{"agent_role":"coder"}},{"id":"n4","type":"output","label":"输出"}],"edges":[{"source_id":"n1","target_id":"n2"},{"source_id":"n2","target_id":"n3"},{"source_id":"n3","target_id":"n4"}]}'

curl -s -X POST "$API/workflows" \
  -H "Content-Type: application/json" \
  -d '{"name":"客户支持问答","nodes":[{"id":"i1","type":"input","label":"问题输入"},{"id":"i2","type":"task","label":"知识检索","config":{"knowledge_enabled":true}},{"id":"i3","type":"output","label":"回答"}],"edges":[{"source_id":"i1","target_id":"i2"},{"source_id":"i2","target_id":"i3"}]}'

curl -s -X POST "$API/workflows" \
  -H "Content-Type: application/json" \
  -d '{"name":"多智能体辩论","nodes":[{"id":"d1","type":"input","label":"议题"},{"id":"d2","type":"task","label":"辩论","config":{"multi_agent_mode":"debate","max_debate_rounds":3}},{"id":"d3","type":"output","label":"共识"}],"edges":[{"source_id":"d1","target_id":"d2"},{"source_id":"d2","target_id":"d3"}]}'

echo "==> Setup complete"
