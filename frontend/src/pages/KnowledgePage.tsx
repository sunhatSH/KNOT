import { useState, useMemo } from 'react';
import {
  Button, Table, Modal, Form, Input, Tabs, Card, List, Tag,
  Typography, Spin, Empty, Alert, Space, message, Select,
  Upload, Progress, Divider,
} from 'antd';
import {
  PlusOutlined, FileTextOutlined, InboxOutlined,
  UploadOutlined, DatabaseOutlined,
} from '@ant-design/icons';
import { knowledgeApi } from '@/api/client';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;

interface KnowledgeCollection {
  name: string;
  description?: string;
  chunkCount: number;
  createdAt: string;
  dimension: number;
}

interface SearchResultItem {
  document_id: string;
  content: string;
  score: number;
  metadata?: Record<string, unknown>;
}

interface UploadResult {
  document_id: string;
  chunks_created: number;
  collection: string;
  filename: string;
}

interface UploadedDocument {
  id: string;
  filename: string;
  chunksCreated: number;
  collection: string;
  uploadedAt: string;
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

  // Upload tab
  const [uploadCollection, setUploadCollection] = useState<string | undefined>(undefined);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

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

  const handleUpload = async () => {
    if (!uploadCollection) {
      message.warning('请先选择知识库');
      return;
    }
    if (!selectedFile) {
      message.warning('请选择要上传的文件');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setUploadError(null);

    // Simulate progress steps — real progress tracking requires
    // an axios onUploadProgress callback, but the response comes only
    // after the entire pipeline finishes on the server.
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => Math.min(prev + 10, 90));
    }, 500);

    try {
      const result: UploadResult = await knowledgeApi.uploadDocument(
        uploadCollection,
        selectedFile,
      );
      clearInterval(progressInterval);
      setUploadProgress(100);

      const doc: UploadedDocument = {
        id: result.document_id,
        filename: result.filename,
        chunksCreated: result.chunks_created,
        collection: result.collection,
        uploadedAt: new Date().toISOString(),
      };
      setUploadedDocs((prev) => [doc, ...prev]);
      message.success(`文档上传成功，已创建 ${result.chunks_created} 个 Chunk`);
      setSelectedFile(null);
    } catch (err: any) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      const detail = err?.response?.data?.detail || err?.message || '上传失败';
      setUploadError(detail);
      message.error(detail);
    } finally {
      setUploading(false);
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

  const uploadDocColumns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    {
      title: 'Chunks',
      dataIndex: 'chunksCreated',
      key: 'chunksCreated',
      width: 100,
    },
    {
      title: '所属知识库',
      dataIndex: 'collection',
      key: 'collection',
    },
    {
      title: '文档 ID',
      dataIndex: 'id',
      key: 'id',
      ellipsis: true,
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '上传时间',
      dataIndex: 'uploadedAt',
      key: 'uploadedAt',
      render: (date: string) => new Date(date).toLocaleString(),
    },
  ];

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
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
          知识库
        </Title>
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
                        <DatabaseOutlined style={{ fontSize: 32, color: '#4f6ef7' }} />
                      </div>
                      <Text type="secondary" style={{ fontSize: 15 }}>
                        暂无知识库，点击上方按钮创建
                      </Text>
                    </div>
                  ) : (
                    <Table
                      dataSource={collections}
                      columns={tableColumns}
                      rowKey="name"
                      pagination={false}
                      style={{ background: '#fff', borderRadius: 8 }}
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
              <Card
                style={{
                  borderRadius: 8,
                  border: '1px solid #e8eaf0',
                }}
              >
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
                      <Text strong style={{ fontSize: 14 }}>
                        搜索结果 ({searchResults.length} 条)
                      </Text>
                      <List
                        dataSource={searchResults}
                        renderItem={(item: SearchResultItem) => (
                          <List.Item style={{ padding: '12px 0' }}>
                            <List.Item.Meta
                              title={
                                <Space>
                                  <FileTextOutlined style={{ color: '#4f6ef7' }} />
                                  <Text code>{item.document_id}</Text>
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
                                <Paragraph ellipsis={{ rows: 3 }} style={{ margin: 0, fontSize: 13 }}>
                                  {item.content}
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
          {
            key: 'upload',
            label: '上传文档',
            children: (
              <Card
                style={{
                  borderRadius: 8,
                  border: '1px solid #e8eaf0',
                }}
              >
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  {/* Collection selector */}
                  <div>
                    <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 14 }}>
                      选择目标知识库
                    </Text>
                    <Select
                      placeholder="选择知识库"
                      style={{ width: 300 }}
                      options={collectionOptions}
                      value={uploadCollection}
                      onChange={(value) => setUploadCollection(value as string | undefined)}
                      allowClear
                      notFoundContent="暂无知识库，请先创建"
                    />
                  </div>

                  {/* File upload area */}
                  <div>
                    <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 14 }}>
                      选择文件
                    </Text>
                    <Dragger
                      name="file"
                      multiple={false}
                      accept=".txt,.md,.pdf,.docx"
                      showUploadList={false}
                      beforeUpload={(file) => {
                        setSelectedFile(file);
                        return false; // Prevent auto-upload
                      }}
                      onRemove={() => setSelectedFile(null)}
                      style={{ borderRadius: 8 }}
                    >
                      <p className="ant-upload-drag-icon">
                        <InboxOutlined style={{ color: '#4f6ef7' }} />
                      </p>
                      <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                      <p className="ant-upload-hint">
                        支持 .txt, .md, .pdf, .docx 格式
                      </p>
                    </Dragger>
                  </div>

                  {/* Selected file info */}
                  {selectedFile && !uploading && (
                    <Alert
                      type="info"
                      showIcon
                      icon={<FileTextOutlined />}
                      message={
                        <Space>
                          <Text>{selectedFile.name}</Text>
                          <Text type="secondary">
                            ({(selectedFile.size / 1024).toFixed(1)} KB)
                          </Text>
                        </Space>
                      }
                    />
                  )}

                  {/* Upload progress */}
                  {uploading && (
                    <div>
                      <Text style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                        正在处理文档（解析 -> 分块 -> 向量化 -> 存储）...
                      </Text>
                      <Progress percent={uploadProgress} status="active" />
                    </div>
                  )}

                  {/* Upload error */}
                  {uploadError && (
                    <Alert
                      message="上传失败"
                      description={uploadError}
                      type="error"
                      showIcon
                      closable
                      onClose={() => setUploadError(null)}
                    />
                  )}

                  {/* Upload button */}
                  <Space>
                    <Button
                      type="primary"
                      icon={<UploadOutlined />}
                      onClick={handleUpload}
                      loading={uploading}
                      disabled={!selectedFile || !uploadCollection || uploading}
                    >
                      {uploading ? '处理中...' : '上传并处理'}
                    </Button>
                    {selectedFile && !uploading && (
                      <Button onClick={() => setSelectedFile(null)}>取消选择</Button>
                    )}
                  </Space>

                  {/* Uploaded documents list */}
                  {uploadedDocs.length > 0 && (
                    <>
                      <Divider style={{ margin: '16px 0' }} />
                      <Text strong style={{ fontSize: 14 }}>已上传的文档</Text>
                      <Table
                        dataSource={uploadedDocs}
                        columns={uploadDocColumns}
                        rowKey="id"
                        pagination={false}
                        size="small"
                      />
                    </>
                  )}

                  {uploadedDocs.length === 0 && !uploading && (
                    <Empty
                      description="暂无上传记录"
                      style={{ marginTop: 24 }}
                    />
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
