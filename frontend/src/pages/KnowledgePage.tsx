import { useState, useMemo } from 'react';
import {
  Button, Table, Modal, Form, Input, Tabs, Card, List, Tag,
  Typography, Spin, Empty, Alert, Space, message, Select,
} from 'antd';
import { PlusOutlined, FileTextOutlined } from '@ant-design/icons';
import { knowledgeApi } from '@/api/client';

const { Title, Text, Paragraph } = Typography;

interface KnowledgeCollection {
  name: string;
  description?: string;
  chunkCount: number;
  createdAt: string;
  dimension: number;
}

interface SearchResultItem {
  id: string;
  text: string;
  score: number;
  metadata?: Record<string, unknown>;
}

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState('collections');
  const [collections, setCollections] = useState<KnowledgeCollection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create modal
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [form] = Form.useForm();

  // Search tab
  const [searchCollection, setSearchCollection] = useState<string | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const collectionOptions = useMemo(
    () => collections.map((c) => ({ label: c.name, value: c.name })),
    [collections],
  );

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setCreateLoading(true);
      await knowledgeApi.createCollection(values.name, 1024);
      const newCollection: KnowledgeCollection = {
        name: values.name,
        description: values.description || '',
        chunkCount: 0,
        createdAt: new Date().toISOString(),
        dimension: 1024,
      };
      setCollections((prev) => [...prev, newCollection]);
      message.success('知识库创建成功');
      setCreateOpen(false);
      form.resetFields();
    } catch (err: any) {
      if (err.errorFields) return; // form validation error, do nothing
      message.error(err?.response?.data?.detail || '创建知识库失败');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchCollection) {
      message.warning('请先选择知识库');
      return;
    }
    if (!searchQuery.trim()) {
      message.warning('请输入搜索关键词');
      return;
    }
    setSearchLoading(true);
    setSearchError(null);
    setSearched(true);
    try {
      const res = await knowledgeApi.search(searchCollection, searchQuery.trim());
      const data = res.data as any;
      // Handle both { results: [...] } and direct array response shapes
      const results: SearchResultItem[] = data?.results ?? data ?? [];
      setSearchResults(results);
    } catch (err: any) {
      setSearchError(err?.response?.data?.detail || '搜索失败');
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };

  const tableColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: 'Chunks',
      dataIndex: 'chunkCount',
      key: 'chunkCount',
      sorter: (a: KnowledgeCollection, b: KnowledgeCollection) => a.chunkCount - b.chunkCount,
    },
    { title: '向量维度', dataIndex: 'dimension', key: 'dimension' },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      render: (date: string) => new Date(date).toLocaleString(),
    },
  ];

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3}>知识库</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建知识库
        </Button>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'collections',
            label: '知识库列表',
            children: (
              <>
                {error && (
                  <Alert
                    message={error}
                    type="error"
                    showIcon
                    style={{ marginBottom: 16 }}
                    closable
                    onClose={() => setError(null)}
                  />
                )}
                <Spin spinning={loading}>
                  {collections.length === 0 && !loading ? (
                    <Empty description="暂无知识库，点击上方按钮创建" />
                  ) : (
                    <Table
                      dataSource={collections}
                      columns={tableColumns}
                      rowKey="name"
                      pagination={false}
                    />
                  )}
                </Spin>
              </>
            ),
          },
          {
            key: 'search',
            label: '搜索',
            children: (
              <Card>
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <Select
                    placeholder="选择知识库"
                    style={{ width: 300 }}
                    options={collectionOptions}
                    value={searchCollection}
                    onChange={(value) => setSearchCollection(value as string | undefined)}
                    allowClear
                    notFoundContent="暂无知识库，请先创建"
                  />

                  <Input.Search
                    placeholder="输入搜索关键词..."
                    enterButton="搜索"
                    size="large"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onSearch={handleSearch}
                    loading={searchLoading}
                  />

                  {searchError && (
                    <Alert
                      message={searchError}
                      type="error"
                      showIcon
                      closable
                      onClose={() => setSearchError(null)}
                    />
                  )}

                  {searched && !searchLoading && !searchError && searchResults.length === 0 && (
                    <Empty description="未找到相关结果" />
                  )}

                  {searchLoading && (
                    <div style={{ textAlign: 'center', padding: 40 }}>
                      <Spin tip="搜索中..." />
                    </div>
                  )}

                  {!searchLoading && searchResults.length > 0 && (
                    <>
                      <Text strong>搜索结果 ({searchResults.length} 条)</Text>
                      <List
                        dataSource={searchResults}
                        renderItem={(item: SearchResultItem) => (
                          <List.Item>
                            <List.Item.Meta
                              title={
                                <Space>
                                  <FileTextOutlined />
                                  <Text code>{item.id}</Text>
                                  <Tag
                                    color={
                                      item.score > 0.8
                                        ? 'green'
                                        : item.score > 0.5
                                          ? 'orange'
                                          : 'default'
                                    }
                                  >
                                    {(item.score * 100).toFixed(1)}%
                                  </Tag>
                                </Space>
                              }
                              description={
                                <Paragraph ellipsis={{ rows: 3 }}>
                                  {item.text}
                                </Paragraph>
                              }
                            />
                          </List.Item>
                        )}
                      />
                    </>
                  )}
                </Space>
              </Card>
            ),
          },
        ]}
      />

      <Modal
        title="新建知识库"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => {
          setCreateOpen(false);
          form.resetFields();
        }}
        confirmLoading={createLoading}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="知识库名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="可选描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
