import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  Modal,
  Row,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  AppstoreOutlined,
  BankOutlined,
  ControlOutlined,
  FileSearchOutlined,
  RocketOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { templateApi } from '@/api/client';
import type { WorkflowTemplate } from '@/types';

const { Text, Title } = Typography;

// ─── Helpers ───────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  general: '通用',
  ops: '运维监控',
  finance: '金融合规',
  medical: '医疗健康',
  custom: '自定义',
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  general: <ControlOutlined />,
  ops: <RocketOutlined />,
  finance: <BankOutlined />,
  medical: <FileSearchOutlined />,
  custom: <AppstoreOutlined />,
};

const CATEGORY_COLORS: Record<string, string> = {
  general: '#8e95a3',
  ops: '#4f6ef7',
  finance: '#52c41a',
  medical: '#eb2f96',
  custom: '#fa8c16',
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

// ─── Component ─────────────────────────────────────────────────────────────

interface TemplateSelectorProps {
  open: boolean;
  onClose: () => void;
}

export default function TemplateSelector({ open, onClose }: TemplateSelectorProps) {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [instantiating, setInstantiating] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');

  // ── Fetch templates ────────────────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    templateApi
      .list()
      .then(setTemplates)
      .catch(() => message.error('加载模板失败'))
      .finally(() => setLoading(false));
  }, [open]);

  // ── Filtered + grouped ─────────────────────────────────────────────────
  const filtered = useMemo(() => {
    if (!searchText.trim()) return templates;
    const q = searchText.toLowerCase();
    return templates.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        (t.description || '').toLowerCase().includes(q) ||
        (t.tags || []).some((tag) => tag.toLowerCase().includes(q)),
    );
  }, [templates, searchText]);

  const grouped = useMemo(() => groupByCategory(filtered), [filtered]);

  // ── Instantiate handler ────────────────────────────────────────────────
  const handleUse = async (template: WorkflowTemplate) => {
    setInstantiating(template.id);
    try {
      const workflow = await templateApi.instantiate(template.id);
      message.success(`已从模板「${template.name}」创建新工作流`);
      onClose();
      navigate(`/workflows/${workflow.id}`);
    } catch (e: any) {
      message.error(`创建工作流失败: ${e.message}`);
    } finally {
      setInstantiating(null);
    }
  };

  // ── Category order ─────────────────────────────────────────────────────
  const categoryOrder = ['general', 'ops', 'finance', 'medical', 'custom'];
  const sortedCategories = Object.keys(grouped).sort(
    (a, b) => categoryOrder.indexOf(a) - categoryOrder.indexOf(b),
  );

  return (
    <Modal
      title={
        <span style={{ fontSize: 16, fontWeight: 600 }}>
          <AppstoreOutlined style={{ marginRight: 8 }} />
          从模板创建工作流
        </span>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={720}
      styles={{
        body: {
          maxHeight: '70vh',
          overflowY: 'auto',
          paddingTop: 8,
        },
      }}
    >
      {/* Search */}
      <div style={{ marginBottom: 16 }}>
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--text-secondary)' }} />}
          placeholder="搜索模板名称、描述或标签……"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          style={{ borderRadius: 6 }}
        />
      </div>

      <Spin spinning={loading}>
        {filtered.length === 0 && !loading ? (
          <div style={{ padding: '40px 0' }}>
            <Empty description={searchText ? '无匹配模板' : '暂无可用模板'} />
          </div>
        ) : (
          sortedCategories.map((cat) => (
            <div key={cat} style={{ marginBottom: 20 }}>
              {/* Section header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <span style={{ color: CATEGORY_COLORS[cat] || '#8e95a3', fontSize: 18 }}>
                  {CATEGORY_ICONS[cat] || <ControlOutlined />}
                </span>
                <Title level={5} style={{ margin: 0, fontWeight: 600 }}>
                  {CATEGORY_LABELS[cat] || cat}
                </Title>
                <Tag style={{ marginLeft: 'auto', borderRadius: 4 }}>
                  {grouped[cat].length} 个模板
                </Tag>
              </div>

              <Row gutter={[12, 12]}>
                {grouped[cat].map((tpl) => (
                  <Col key={tpl.id} xs={24} sm={12}>
                    <Card
                      size="small"
                      style={{
                        borderRadius: 8,
                        border: '1px solid var(--border-color)',
                        background: 'var(--bg-card)',
                        height: '100%',
                      }}
                      actions={[
                        <Button
                          key="use"
                          type="primary"
                          size="small"
                          loading={instantiating === tpl.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleUse(tpl);
                          }}
                          style={{
                            borderRadius: 6,
                            fontSize: 13,
                          }}
                        >
                          使用此模板
                        </Button>,
                      ]}
                    >
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
                              ellipsis
                              style={{
                                display: 'block',
                                marginBottom: 10,
                                fontSize: 12,
                                lineHeight: 1.5,
                                color: 'var(--text-secondary)',
                              }}
                            >
                              {tpl.description || '暂无描述'}
                            </Text>
                            <div
                              style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: 4,
                                marginBottom: 6,
                              }}
                            >
                              {(tpl.tags || []).slice(0, 3).map((tag) => (
                                <Tag key={tag} style={{ fontSize: 11, borderRadius: 4, margin: 0 }}>
                                  {tag}
                                </Tag>
                              ))}
                              {(tpl.tags || []).length > 3 && (
                                <Tag style={{ fontSize: 11, borderRadius: 4, margin: 0 }}>
                                  +{tpl.tags.length - 3}
                                </Tag>
                              )}
                            </div>
                            <Text
                              type="secondary"
                              style={{ fontSize: 11, color: 'var(--text-secondary)' }}
                            >
                              已使用 {tpl.usage_count} 次
                            </Text>
                          </div>
                        }
                      />
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          ))
        )}
      </Spin>
    </Modal>
  );
}
