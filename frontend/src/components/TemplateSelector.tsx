import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Empty,
  Input,
  Modal,
  Row,
  Skeleton,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  ApiOutlined,
  AppstoreOutlined,
  BankOutlined,
  ControlOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  NodeIndexOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  RocketOutlined,
  SearchOutlined,
  TeamOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { templateApi } from '@/api/client';
import type { WorkflowTemplate } from '@/types';

const { Text, Title, Paragraph } = Typography;

// ─── Helpers ───────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  general: 'General',
  ops: 'IT Operations',
  finance: 'Financial Compliance',
  medical: 'Healthcare',
  custom: 'Custom',
  data: 'Data Processing',
  support: 'Customer Service',
  multi_agent: 'Multi-Agent',
  monitoring: 'Monitoring',
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  general: <ControlOutlined />,
  ops: <RocketOutlined />,
  finance: <BankOutlined />,
  medical: <FileSearchOutlined />,
  custom: <AppstoreOutlined />,
  data: <DatabaseOutlined />,
  support: <QuestionCircleOutlined />,
  multi_agent: <TeamOutlined />,
  monitoring: <WarningOutlined />,
};

const CATEGORY_COLORS: Record<string, string> = {
  general: '#8e95a3',
  ops: '#4f6ef7',
  finance: '#52c41a',
  medical: '#eb2f96',
  custom: '#fa8c16',
  data: '#722ed1',
  support: '#13c2c2',
  multi_agent: '#f5222d',
  monitoring: '#fa8c16',
};

const NODE_TYPE_LABELS: Record<string, string> = {
  input: 'Input',
  output: 'Output',
  task: 'Task',
  condition: 'Condition',
  parallel: 'Parallel',
  loop: 'Loop',
};

const NODE_TYPE_COLORS: Record<string, string> = {
  input: 'blue',
  output: 'green',
  task: 'orange',
  condition: 'pink',
  parallel: 'purple',
  loop: 'cyan',
};

function groupByCategory(
  templates: WorkflowTemplate[],
): Record<string, WorkflowTemplate[]> {
  const groups: Record<string, WorkflowTemplate[]> = {};
  for (const t of templates) {
    const cat = t.category || 'general';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(t);
  }
  return groups;
}

const CATEGORY_ORDER = [
  'general', 'data', 'multi_agent', 'ops', 'monitoring',
  'support', 'finance', 'medical', 'custom',
];

// ─── Component ─────────────────────────────────────────────────────────────

interface TemplateSelectorProps {
  open: boolean;
  onClose: () => void;
}

export default function TemplateSelector({ open, onClose }: TemplateSelectorProps) {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [instantiating, setInstantiating] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [previewTemplate, setPreviewTemplate] = useState<WorkflowTemplate | null>(null);

  // ── Fetch templates ────────────────────────────────────────────────────
  const fetchTemplates = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await templateApi.list();
      setTemplates(data);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Unknown error';
      setError(msg);
      message.error('Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    fetchTemplates();
  }, [open]);

  // ── Filtered + grouped ─────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let result = templates;

    // Category filter
    if (activeCategory !== 'all') {
      result = result.filter((t) => (t.category || 'general') === activeCategory);
    }

    // Search filter
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      result = result.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          (t.description || '').toLowerCase().includes(q) ||
          (t.tags || []).some((tag) => tag.toLowerCase().includes(q)),
      );
    }

    return result;
  }, [templates, searchText, activeCategory]);

  const grouped = useMemo(() => groupByCategory(filtered), [filtered]);

  // ── Category tab items ─────────────────────────────────────────────────
  const categoryTabs = useMemo(() => {
    const allGroups = groupByCategory(templates);

    // Compute counts for all categories
    const counts: Record<string, number> = {};
    for (const [cat, tpls] of Object.entries(allGroups)) {
      counts[cat] = tpls.length;
    }
    const totalCount = templates.length;

    const tabItems = [
      {
        key: 'all',
        label: (
          <span>
            <AppstoreOutlined style={{ marginRight: 6 }} />
            All ({totalCount})
          </span>
        ),
      },
      ...CATEGORY_ORDER.filter((cat) => counts[cat]).map((cat) => ({
        key: cat,
        label: (
          <span>
            <span style={{ color: CATEGORY_COLORS[cat] || '#8e95a3', marginRight: 6 }}>
              {CATEGORY_ICONS[cat] || <ControlOutlined />}
            </span>
            {CATEGORY_LABELS[cat] || cat} ({counts[cat]})
          </span>
        ),
      })),
      // Any remaining (uncategorized) categories
      ...Object.keys(allGroups)
        .filter((cat) => !CATEGORY_ORDER.includes(cat))
        .map((cat) => ({
          key: cat,
          label: (
            <span>
              <ControlOutlined style={{ marginRight: 6 }} />
              {cat} ({counts[cat]})
            </span>
          ),
        })),
    ];

    return tabItems;
  }, [templates]);

  // ── Instantiate handler ────────────────────────────────────────────────
  const handleUse = async (template: WorkflowTemplate) => {
    setInstantiating(template.id);
    try {
      const workflow = await templateApi.instantiate(template.id);
      message.success(`Created workflow from template "${template.name}"`);
      onClose();
      navigate(`/workflows/${workflow.id}`);
    } catch (e: any) {
      message.error(`Failed to create workflow: ${e.message}`);
    } finally {
      setInstantiating(null);
    }
  };

  // ── Sorted categories for display ──────────────────────────────────────
  const sortedCategories = Object.keys(grouped).sort(
    (a, b) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b),
  );

  // ── Render: Error state ─────────────────────────────────────────────────
  const renderError = () => (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 24px',
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 32,
          background: '#fff1f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 16,
        }}
      >
        <WarningOutlined style={{ fontSize: 28, color: '#ff4d4f' }} />
      </div>
      <Text type="secondary" style={{ marginBottom: 16, textAlign: 'center' }}>
        Failed to load templates: {error}
      </Text>
      <Button icon={<ReloadOutlined />} onClick={fetchTemplates}>
        Retry
      </Button>
    </div>
  );

  // ── Render: Loading skeleton ────────────────────────────────────────────
  const renderSkeleton = () => (
    <div style={{ padding: '16px 0' }}>
      <Skeleton active paragraph={{ rows: 1 }} title={{ width: '30%' }} />
      <Row gutter={[12, 12]} style={{ marginTop: 12 }}>
        {[1, 2, 3].map((i) => (
          <Col key={i} xs={24} sm={12}>
            <Card size="small">
              <Skeleton active paragraph={{ rows: 2 }} />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );

  // ── Render: Template grid ──────────────────────────────────────────────
  const renderTemplateGrid = (tpls: WorkflowTemplate[]) => (
    <Row gutter={[12, 12]}>
      {tpls.map((tpl) => (
        <Col key={tpl.id} xs={24} sm={12}>
          <Card
            size="small"
            hoverable
            onClick={() => setPreviewTemplate(tpl)}
            style={{
              borderRadius: 8,
              border: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
              height: '100%',
              cursor: 'pointer',
              transition: 'box-shadow 0.2s',
            }}
            styles={{
              body: { padding: 14 },
            }}
            actions={[
              <div
                key="node-count"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                  padding: '4px 0',
                }}
              >
                <NodeIndexOutlined />
                {tpl.nodes.length} nodes
              </div>,
              <Button
                key="use"
                type="primary"
                size="small"
                loading={instantiating === tpl.id}
                onClick={(e) => {
                  e.stopPropagation();
                  handleUse(tpl);
                }}
                style={{ borderRadius: 6, fontSize: 13 }}
              >
                Use Template
              </Button>,
            ]}
          >
            {/* Category tag */}
            <div style={{ marginBottom: 8 }}>
              <Tag
                style={{
                  borderRadius: 4,
                  fontSize: 11,
                  margin: 0,
                  color: CATEGORY_COLORS[tpl.category] || '#8e95a3',
                  borderColor: CATEGORY_COLORS[tpl.category] || '#8e95a3',
                  background: `${CATEGORY_COLORS[tpl.category] || '#8e95a3'}15`,
                }}
              >
                <span style={{ marginRight: 4 }}>
                  {CATEGORY_ICONS[tpl.category] || <ControlOutlined />}
                </span>
                {CATEGORY_LABELS[tpl.category] || tpl.category}
              </Tag>
            </div>

            <Card.Meta
              title={
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: 'var(--text-primary, #1a1d29)',
                  }}
                >
                  {tpl.name}
                </span>
              }
              description={
                <div>
                  <Text
                    type="secondary"
                    ellipsis={{ rows: 2 }}
                    style={{
                      display: 'block',
                      marginBottom: 10,
                      fontSize: 12,
                      lineHeight: 1.5,
                      color: 'var(--text-secondary)',
                      minHeight: 36,
                    }}
                  >
                    {tpl.description || 'No description'}
                  </Text>

                  {/* Tags */}
                  {(tpl.tags || []).length > 0 && (
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 4,
                        marginBottom: 6,
                      }}
                    >
                      {(tpl.tags || []).slice(0, 3).map((tag) => (
                        <Tag
                          key={tag}
                          style={{
                            fontSize: 11,
                            borderRadius: 4,
                            margin: 0,
                            lineHeight: '20px',
                          }}
                        >
                          {tag}
                        </Tag>
                      ))}
                      {(tpl.tags || []).length > 3 && (
                        <Tag style={{ fontSize: 11, borderRadius: 4, margin: 0 }}>
                          +{tpl.tags.length - 3}
                        </Tag>
                      )}
                    </div>
                  )}

                  {/* Node type summary */}
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 3,
                      marginBottom: 6,
                    }}
                  >
                    {Array.from(new Set(tpl.nodes.map((n) => n.type))).map((nt) => (
                      <Tag
                        key={nt}
                        color={NODE_TYPE_COLORS[nt] || 'default'}
                        style={{ fontSize: 10, borderRadius: 4, margin: 0, lineHeight: '18px' }}
                      >
                        {NODE_TYPE_LABELS[nt] || nt}
                      </Tag>
                    ))}
                  </div>

                  {/* Usage count */}
                  <Text
                    type="secondary"
                    style={{ fontSize: 11, color: 'var(--text-secondary)' }}
                  >
                    Used {tpl.usage_count} time{tpl.usage_count !== 1 ? 's' : ''}
                  </Text>
                </div>
              }
            />
          </Card>
        </Col>
      ))}
    </Row>
  );

  // ── Render: All categories (flat tab view) ─────────────────────────────
  const renderCategorySections = () => (
    <>
      {sortedCategories.map((cat) => (
        <div key={cat} style={{ marginBottom: 24 }}>
          {/* Section header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 12,
              padding: '0 4px',
            }}
          >
            <span
              style={{
                color: CATEGORY_COLORS[cat] || '#8e95a3',
                fontSize: 18,
              }}
            >
              {CATEGORY_ICONS[cat] || <ControlOutlined />}
            </span>
            <Title level={5} style={{ margin: 0, fontWeight: 600 }}>
              {CATEGORY_LABELS[cat] || cat}
            </Title>
            <Tag
              style={{
                marginLeft: 'auto',
                borderRadius: 4,
                fontSize: 12,
              }}
            >
              {grouped[cat].length} template{grouped[cat].length !== 1 ? 's' : ''}
            </Tag>
          </div>
          {renderTemplateGrid(grouped[cat])}
        </div>
      ))}
    </>
  );

  // ── Render: Preview modal ──────────────────────────────────────────────
  const renderPreviewModal = () => (
    <Modal
      title={
        <span style={{ fontSize: 16, fontWeight: 600 }}>
          <FileSearchOutlined style={{ marginRight: 8 }} />
          {previewTemplate?.name || 'Template Preview'}
        </span>
      }
      open={previewTemplate !== null}
      onCancel={() => setPreviewTemplate(null)}
      footer={
        previewTemplate ? [
          <Button key="cancel" onClick={() => setPreviewTemplate(null)}>
            Close
          </Button>,
          <Button
            key="use"
            type="primary"
            loading={instantiating === previewTemplate.id}
            onClick={() => {
              const tpl = previewTemplate;
              setPreviewTemplate(null);
              handleUse(tpl);
            }}
          >
            Use This Template
          </Button>,
        ] : []
      }
      width={640}
    >
      {previewTemplate && (
        <div>
          {/* Category and tags */}
          <Space style={{ marginBottom: 16 }} wrap>
            <Tag
              color={CATEGORY_COLORS[previewTemplate.category] || '#8e95a3'}
              style={{ borderRadius: 4 }}
            >
              {CATEGORY_ICONS[previewTemplate.category] || <ControlOutlined />}
              {' '}
              {CATEGORY_LABELS[previewTemplate.category] || previewTemplate.category}
            </Tag>
            {previewTemplate.tags.map((tag) => (
              <Tag key={tag} style={{ borderRadius: 4 }}>
                {tag}
              </Tag>
            ))}
          </Space>

          {/* Description */}
          <Paragraph
            style={{ marginBottom: 16, color: 'var(--text-secondary)' }}
          >
            {previewTemplate.description || 'No description'}
          </Paragraph>

          <Divider style={{ margin: '12px 0' }} />

          {/* Workflow config */}
          {Object.keys(previewTemplate.config || {}).length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                Configuration
              </Text>
              <Descriptions column={1} size="small" bordered>
                {Object.entries(previewTemplate.config).slice(0, 6).map(([key, value]) => (
                  <Descriptions.Item key={key} label={key}>
                    {typeof value === 'object'
                      ? JSON.stringify(value)
                      : String(value)}
                  </Descriptions.Item>
                ))}
                {Object.keys(previewTemplate.config).length > 6 && (
                  <Descriptions.Item label="...">
                    +{Object.keys(previewTemplate.config).length - 6} more
                  </Descriptions.Item>
                )}
              </Descriptions>
            </div>
          )}

          {/* Nodes list */}
          <div style={{ marginBottom: 16 }}>
            <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
              Nodes ({previewTemplate.nodes.length})
            </Text>
            {previewTemplate.nodes.map((node, idx) => (
              <div
                key={node.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 8px',
                  marginBottom: 4,
                  borderRadius: 6,
                  background: 'var(--bg-canvas, #f5f6fa)',
                }}
              >
                <Tag
                  color={NODE_TYPE_COLORS[node.type] || 'default'}
                  style={{ margin: 0, borderRadius: 4, minWidth: 60, textAlign: 'center', fontSize: 11 }}
                >
                  {NODE_TYPE_LABELS[node.type] || node.type}
                </Tag>
                <Text style={{ fontSize: 13, flex: 1 }}>
                  {idx + 1}. {node.label || node.id}
                </Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {node.agent_id ? `Agent: ${node.agent_id}` : ''}
                </Text>
              </div>
            ))}
          </div>

          {/* Edges list */}
          {previewTemplate.edges.length > 0 && (
            <div>
              <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
                Connections ({previewTemplate.edges.length})
              </Text>
              {previewTemplate.edges.map((edge) => (
                <div
                  key={edge.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 8px',
                    marginBottom: 2,
                    borderRadius: 4,
                    fontSize: 12,
                    color: 'var(--text-secondary)',
                  }}
                >
                  <ApiOutlined style={{ fontSize: 11 }} />
                  <Text code style={{ fontSize: 11 }}>
                    {edge.source_id}
                  </Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>→</Text>
                  <Text code style={{ fontSize: 11 }}>
                    {edge.target_id}
                  </Text>
                  {edge.label && (
                    <Tag
                      style={{ fontSize: 10, margin: 0, borderRadius: 3 }}
                    >
                      {edge.label}
                    </Tag>
                  )}
                  {edge.condition && (
                    <Text
                      type="secondary"
                      style={{ fontSize: 10, fontStyle: 'italic' }}
                    >
                      if: {edge.condition}
                    </Text>
                  )}
                </div>
              ))}
            </div>
          )}

          <Divider style={{ margin: '16px 0' }} />

          {/* Metadata */}
          <Descriptions column={2} size="small">
            <Descriptions.Item label="Template ID">
              <Text code style={{ fontSize: 11 }}>
                {previewTemplate.id}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="Usage count">
              {previewTemplate.usage_count}
            </Descriptions.Item>
            <Descriptions.Item label="Created">
              {new Date(previewTemplate.created_at).toLocaleDateString()}
            </Descriptions.Item>
            <Descriptions.Item label="Updated">
              {new Date(previewTemplate.updated_at).toLocaleDateString()}
            </Descriptions.Item>
          </Descriptions>
        </div>
      )}
    </Modal>
  );

  // ── Main render ────────────────────────────────────────────────────────
  return (
    <>
      <Modal
        title={
          <span style={{ fontSize: 16, fontWeight: 600 }}>
            <AppstoreOutlined style={{ marginRight: 8 }} />
            Template Marketplace
          </span>
        }
        open={open}
        onCancel={onClose}
        footer={null}
        width={780}
        styles={{
          body: {
            maxHeight: '75vh',
            overflowY: 'auto',
            paddingTop: 8,
          },
        }}
      >
        {/* Category tabs */}
        <Tabs
          activeKey={activeCategory}
          onChange={setActiveCategory}
          items={categoryTabs}
          size="small"
          style={{ marginBottom: 12 }}
          tabBarStyle={{ marginBottom: 12 }}
        />

        {/* Search bar */}
        <div style={{ marginBottom: 16 }}>
          <Input
            prefix={
              <SearchOutlined style={{ color: 'var(--text-secondary)' }} />
            }
            placeholder="Search templates by name, description, or tags..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
            style={{ borderRadius: 6 }}
          />
        </div>

        {/* Content */}
        <Spin spinning={loading}>
          {error && !loading ? (
            renderError()
          ) : loading ? (
            renderSkeleton()
          ) : filtered.length === 0 ? (
            <div style={{ padding: '40px 0' }}>
              <Empty
                description={
                  searchText || activeCategory !== 'all'
                    ? 'No templates match your filters'
                    : 'No templates available yet'
                }
              >
                {(searchText || activeCategory !== 'all') && (
                  <Button
                    size="small"
                    onClick={() => {
                      setSearchText('');
                      setActiveCategory('all');
                    }}
                  >
                    Clear Filters
                  </Button>
                )}
              </Empty>
            </div>
          ) : activeCategory === 'all' ? (
            renderCategorySections()
          ) : (
            renderTemplateGrid(filtered)
          )}
        </Spin>
      </Modal>

      {/* Preview modal */}
      {renderPreviewModal()}
    </>
  );
}
