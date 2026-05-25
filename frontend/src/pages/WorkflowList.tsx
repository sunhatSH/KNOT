import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Col, Row, Spin, Tag, Typography, Empty } from 'antd';
import { PlusOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { workflowApi } from '@/api/client';
import { useWorkflowStore } from '@/store/workflowStore';
import { useMediaQuery } from '@/hooks/useMediaQuery';

const { Title, Text } = Typography;

const statusColors: Record<string, string> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  pending: 'default',
};

export default function WorkflowList() {
  const navigate = useNavigate();
  const { workflows, loading, setWorkflows, setLoading } = useWorkflowStore();
  const isMobile = useMediaQuery('(max-width: 768px)');

  const loadWorkflows = async () => {
    setLoading(true);
    try {
      const data = await workflowApi.list();
      setWorkflows(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkflows();
  }, []);

  return (
    <div style={{ padding: isMobile ? 12 : 24, maxWidth: 1200, margin: '0 auto' }}>
      {/* Page header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          工作流
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/workflows/new')}>
          新建工作流
        </Button>
      </div>

      <Spin spinning={loading}>
        {workflows.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '80px 24px',
              background: '#fff',
              borderRadius: 8,
              border: '1px solid #e8eaf0',
            }}
          >
            <div
              style={{
                width: 80,
                height: 80,
                borderRadius: 40,
                background: '#f0f2ff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 16,
              }}
            >
              <NodeIndexOutlined style={{ fontSize: 32, color: '#4f6ef7' }} />
            </div>
            <Text type="secondary" style={{ fontSize: 15, marginBottom: 16 }}>
              暂无工作流，点击上方按钮创建
            </Text>
          </div>
        ) : (
          <Row gutter={[16, 16]}>
            {workflows.map((wf) => (
              <Col key={wf.id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  hoverable
                  onClick={() => navigate(`/workflows/${wf.id}`)}
                  style={{ borderRadius: 8, border: '1px solid #e8eaf0' }}
                  actions={[
                    <NodeIndexOutlined key="edit" style={{ color: '#4f6ef7' }} />,
                  ]}
                >
                  <Card.Meta
                    title={
                      <span style={{ fontSize: 15, fontWeight: 600, color: '#1a1d29' }}>
                        {wf.name}
                      </span>
                    }
                    description={
                      <>
                        <Text
                          type="secondary"
                          ellipsis
                          style={{ display: 'block', marginBottom: 12, fontSize: 13 }}
                        >
                          {wf.description || '无描述'}
                        </Text>
                        <div>
                          <Tag style={{ margin: 0 }}>{wf.nodes?.length || 0} 个节点</Tag>
                          {wf.tags?.map((t) => (
                            <Tag key={t} style={{ marginLeft: 4 }}>
                              {t}
                            </Tag>
                          ))}
                        </div>
                      </>
                    }
                  />
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>
    </div>
  );
}
