import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Col, Row, Spin, Tag, Typography, Empty } from 'antd';
import { PlusOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { workflowApi } from '@/api/client';
import { useWorkflowStore } from '@/store/workflowStore';

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
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3}>工作流</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/workflows/new')}>
          新建工作流
        </Button>
      </div>

      <Spin spinning={loading}>
        {workflows.length === 0 ? (
          <Empty description="暂无工作流，点击上方按钮创建" />
        ) : (
          <Row gutter={[16, 16]}>
            {workflows.map((wf) => (
              <Col key={wf.id} xs={24} sm={12} md={8} lg={6}>
                <Card
                  hoverable
                  onClick={() => navigate(`/workflows/${wf.id}`)}
                  actions={[<NodeIndexOutlined key="edit" />]}
                >
                  <Card.Meta
                    title={wf.name}
                    description={
                      <>
                        <Text type="secondary" ellipsis style={{ display: 'block', marginBottom: 8 }}>
                          {wf.description || '无描述'}
                        </Text>
                        <div>
                          <Tag>{wf.nodes?.length || 0} 个节点</Tag>
                          {wf.tags?.map((t) => (
                            <Tag key={t}>{t}</Tag>
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
