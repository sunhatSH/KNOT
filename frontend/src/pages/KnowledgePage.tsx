import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Button, Table, Modal, Form, Input, Tabs, Card, List, Tag,
  Typography, Spin, Empty, Alert, Space, message, Select,
  Upload, Progress, Divider, Popconfirm, Row, Col, Collapse,
} from 'antd';
import {
  PlusOutlined, FileTextOutlined, InboxOutlined,
  UploadOutlined, DatabaseOutlined,
  DeleteOutlined, EyeOutlined, SearchOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons';
import { knowledgeApi } from '@/api/client';
import { useMediaQuery } from '@/hooks/useMediaQuery';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;

// ─── Interfaces ─────────────────────────────────────────────────────────────

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

interface KnowledgeDocument {
  id: string;
  filename: string;
  type?: string;
  size?: number;
  chunks?: number;
  collection: string;
  uploaded_at: string;
}

interface DocumentPreview {
  id: string;
  filename: string;
  type?: string;
  size?: number;
  chunks?: number;
  collection: string;
  uploaded_at: string;
  content?: string;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const DOCUMENT_TYPES = [
  { value: 'txt', label: 'TXT' },
  { value: 'pdf', label: 'PDF' },
  { value: 'md', label: 'Markdown' },
  { value: 'docx', label: 'DOCX' },
];

const PAGE_SIZE_OPTIONS = ['10', '20', '50'];

// ─── Helper: format file size ──────────────────────────────────────────────

function formatFileSize(bytes?: number): string {
  if (bytes == null) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ─── Helper: format timestamp ──────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// ─── Main Component ─────────────────────────────────────────────────────────

export default function KnowledgePage() {
  const isMobile = useMediaQuery('(max-width: 768px)');

  // ── Navigation ───────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('collections');

  // ── Collections ──────────────────────────────────────────────────────────
  const [collections, setCollections] = useState<KnowledgeCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);
  const [deletingCollection, setDeletingCollection] = useState<string | null>(null);

  // Create collection modal
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [form] = Form.useForm();

  // ── Search ───────────────────────────────────────────────────────────────
  const [searchCollection, setSearchCollection] = useState<string | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchDocType, setSearchDocType] = useState<string | undefined>(undefined);
  const [searchDateFrom, setSearchDateFrom] = useState('');
  const [searchDateTo, setSearchDateTo] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  // ── Document Management ──────────────────────────────────────────────────
  const [docCollection, setDocCollection] = useState<string | undefined>(undefined);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [docPagination, setDocPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [selectedDocIds, setSelectedDocIds] = useState<React.Key[]>([]);
  const [deletingDocIds, setDeletingDocIds] = useState<string[]>([]);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [docSearchQuery, setDocSearchQuery] = useState('');
  const [docTypeFilter, setDocTypeFilter] = useState<string | undefined>(undefined);
  const [docDateFrom, setDocDateFrom] = useState('');
  const [docDateTo, setDocDateTo] = useState('');

  // Document preview
  const [previewDoc, setPreviewDoc] = useState<DocumentPreview | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Upload
  const [uploadCollection, setUploadCollection] = useState<string | undefined>(undefined);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // ── Derived ──────────────────────────────────────────────────────────────
  const collectionOptions = useMemo(
    () => collections.map((c) => ({ label: c.name, value: c.name })),
    [collections],
  );

  // ── Load collections on mount ────────────────────────────────────────────
  const fetchCollections = useCallback(async () => {
    setCollectionsLoading(true);
    setCollectionsError(null);
    try {
      const data = await knowledgeApi.listCollections();
      setCollections(
        (data as any[]).map((c) => ({
          name: c.name,
          description: c.description || '',
          chunkCount: c.chunk_count || 0,
          createdAt: c.created_at,
          dimension: c.dimension || 1024,
        })),
      );
    } catch (err: any) {
      // Backend may not have list endpoint; keep local state
      if (collections.length === 0) {
        setCollectionsError(null); // Suppress error - collections can be created locally
      }
    } finally {
      setCollectionsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  // ── Load documents when collection or filters change ─────────────────────
  const fetchDocuments = useCallback(
    async (page = 1, pageSize = 10) => {
      if (!docCollection) {
        setDocuments([]);
        setDocPagination({ current: 1, pageSize: 10, total: 0 });
        return;
      }
      setDocumentsLoading(true);
      setDocumentsError(null);
      try {
        const data = await knowledgeApi.listDocuments(docCollection, {
          page,
          page_size: pageSize,
          type: docTypeFilter || undefined,
          date_from: docDateFrom || undefined,
          date_to: docDateTo || undefined,
        });
        const result = data as any;
        const docs: KnowledgeDocument[] = (result.documents || result.data || []).map(
          (d: any) => ({
            id: d.id || d.document_id,
            filename: d.filename || d.name || '未知文件',
            type: d.type || d.filename?.split('.').pop() || '未知',
            size: d.size || d.file_size,
            chunks: d.chunks || d.chunk_count || d.chunks_created || 0,
            collection: d.collection || docCollection,
            uploaded_at: d.uploaded_at || d.created_at || new Date().toISOString(),
          }),
        );
        setDocuments(docs);
        setDocPagination({
          current: result.page || page,
          pageSize: result.page_size || pageSize,
          total: result.total || docs.length,
        });
      } catch (err: any) {
        const detail = err?.response?.data?.detail || err?.message || '加载文档列表失败';
        setDocumentsError(detail);
        // Keep existing documents rather than clearing on error
        message.error(detail);
      } finally {
        setDocumentsLoading(false);
      }
    },
    [docCollection, docTypeFilter, docDateFrom, docDateTo],
  );

  // Fetch documents when collection changes or pagination changes
  useEffect(() => {
    if (activeTab === 'documents' || activeTab === 'upload') {
      fetchDocuments(docPagination.current, docPagination.pageSize);
    }
  }, [docCollection, docTypeFilter, docDateFrom, docDateTo, activeTab]);

  // ── Create Collection ────────────────────────────────────────────────────
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

  // ── Delete Collection ────────────────────────────────────────────────────
  const handleDeleteCollection = async (name: string) => {
    setDeletingCollection(name);
    try {
      await knowledgeApi.deleteCollection(name);
      setCollections((prev) => prev.filter((c) => c.name !== name));
      message.success(`知识库「${name}」已删除`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || `删除知识库「${name}」失败`);
    } finally {
      setDeletingCollection(null);
    }
  };

  // ── Manage documents ─────────────────────────────────────────────────────
  const handleManageDocuments = (collectionName: string) => {
    setDocCollection(collectionName);
    setDocPagination({ current: 1, pageSize: 10, total: 0 });
    setActiveTab('documents');
  };

  // ── Search ───────────────────────────────────────────────────────────────
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
      const results: SearchResultItem[] = data?.results ?? data ?? [];
      setSearchResults(results);
    } catch (err: any) {
      setSearchError(err?.response?.data?.detail || '搜索失败');
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };

  // ── Upload ───────────────────────────────────────────────────────────────
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

      // Refresh documents list if viewing the same collection
      if (docCollection === uploadCollection) {
        fetchDocuments(1, docPagination.pageSize);
      }
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

  // ── Document Preview ─────────────────────────────────────────────────────
  const handlePreview = async (doc: KnowledgeDocument) => {
    setPreviewLoading(true);
    setPreviewOpen(true);
    setPreviewDoc({
      id: doc.id,
      filename: doc.filename,
      type: doc.type,
      size: doc.size,
      chunks: doc.chunks,
      collection: doc.collection,
      uploaded_at: doc.uploaded_at,
    });
    try {
      const data = await knowledgeApi.getDocument(doc.collection, doc.id);
      const result = data as any;
      setPreviewDoc({
        id: doc.id,
        filename: result.filename || doc.filename,
        type: result.type || doc.type,
        size: result.size || doc.size,
        chunks: result.chunks || result.chunk_count || doc.chunks,
        collection: result.collection || doc.collection,
        uploaded_at: result.uploaded_at || doc.uploaded_at,
        content: result.content || result.preview || '',
      });
    } catch {
      // Show preview with metadata only (content not available)
      setPreviewDoc((prev) => prev ? { ...prev, content: '(预览内容暂不可用)' } : null);
    } finally {
      setPreviewLoading(false);
    }
  };

  // ── Delete Document ──────────────────────────────────────────────────────
  const handleDeleteDocument = async (collectionName: string, docId: string) => {
    setDeletingDocIds((prev) => [...prev, docId]);
    try {
      await knowledgeApi.deleteDocument(collectionName, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setUploadedDocs((prev) => prev.filter((d) => d.id !== docId));
      setSelectedDocIds((prev) => prev.filter((id) => id !== docId));
      message.success('文档已删除');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除文档失败');
    } finally {
      setDeletingDocIds((prev) => prev.filter((id) => id !== docId));
    }
  };

  // ── Batch Delete ─────────────────────────────────────────────────────────
  const handleBatchDelete = async () => {
    if (!docCollection || selectedDocIds.length === 0) return;
    setBatchDeleting(true);
    try {
      await knowledgeApi.batchDeleteDocuments(
        docCollection,
        selectedDocIds as string[],
      );
      setDocuments((prev) => prev.filter((d) => !selectedDocIds.includes(d.id)));
      setSelectedDocIds([]);
      message.success(`已删除 ${selectedDocIds.length} 个文档`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '批量删除失败');
    } finally {
      setBatchDeleting(false);
    }
  };

  // ── Upload tab collection selector change sync ───────────────────────────
  const handleUploadCollectionChange = (value: string | undefined) => {
    setUploadCollection(value);
    if (value) {
      setDocCollection(value);
    }
  };

  // ── Column definitions ───────────────────────────────────────────────────
  const collectionColumns = [
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
      render: (date: string) => formatDate(date),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: KnowledgeCollection) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<FolderOpenOutlined />}
            onClick={() => handleManageDocuments(record.name)}
          >
            管理文档
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除知识库「${record.name}」吗？所有文档将被移除。`}
            onConfirm={() => handleDeleteCollection(record.name)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={deletingCollection === record.name}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const uploadDocColumns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    {
      title: 'Chunks',
      dataIndex: 'chunksCreated',
      key: 'chunksCreated',
      width: 80,
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
      render: (v: string) => <Text code style={{ fontSize: 11 }}>{v.slice(0, 12)}...</Text>,
    },
    {
      title: '上传时间',
      dataIndex: 'uploadedAt',
      key: 'uploadedAt',
      render: (date: string) => formatDate(date),
    },
  ];

  const docColumns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (v: string, record: KnowledgeDocument) => (
        <Space>
          <FileTextOutlined style={{ color: '#4f6ef7' }} />
          <a onClick={() => handlePreview(record)} style={{ cursor: 'pointer' }}>
            {v}
          </a>
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (v: string) => v ? <Tag>{v.toUpperCase()}</Tag> : '-',
    },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 90,
      render: (v: number) => formatFileSize(v),
    },
    {
      title: 'Chunks',
      dataIndex: 'chunks',
      key: 'chunks',
      width: 70,
    },
    {
      title: '上传时间',
      dataIndex: 'uploaded_at',
      key: 'uploaded_at',
      width: 170,
      render: (v: string) => formatDate(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: KnowledgeDocument) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              handlePreview(record);
            }}
          >
            预览
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除「${record.filename}」吗？`}
            onConfirm={(e) => {
              if (e) e.stopPropagation();
              handleDeleteDocument(record.collection, record.id);
            }}
            onCancel={(e) => e?.stopPropagation()}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              loading={deletingDocIds.includes(record.id)}
              onClick={(e) => e.stopPropagation()}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ── Tab content builders ─────────────────────────────────────────────────

  const renderCollectionsTab = () => (
    <>
      {collectionsError && (
        <Alert
          message={collectionsError}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setCollectionsError(null)}
        />
      )}
      <Spin spinning={collectionsLoading}>
        {!collectionsLoading && collections.length === 0 ? (
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
            <Text type="secondary" style={{ fontSize: 15, marginBottom: 16 }}>
              暂无知识库，点击上方按钮创建
            </Text>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建知识库
            </Button>
          </div>
        ) : (
          <Table
            dataSource={collections}
            columns={collectionColumns}
            rowKey="name"
            pagination={false}
            style={{ background: '#fff', borderRadius: 8 }}
          />
        )}
      </Spin>
    </>
  );

  const renderSearchTab = () => (
    <Card
      style={{
        borderRadius: 8,
        border: '1px solid #e8eaf0',
      }}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* Filters row */}
        <div
          style={{
            display: 'flex',
            gap: 12,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          <Select
            placeholder="选择知识库"
            style={{ width: 200 }}
            options={collectionOptions}
            value={searchCollection}
            onChange={(value) => setSearchCollection(value as string | undefined)}
            allowClear
            notFoundContent="暂无知识库，请先创建"
          />
          <Select
            placeholder="文档类型"
            style={{ width: 140 }}
            options={DOCUMENT_TYPES}
            value={searchDocType}
            onChange={(value) => setSearchDocType(value as string | undefined)}
            allowClear
          />
          <Input
            placeholder="开始日期 (YYYY-MM-DD)"
            style={{ width: 170 }}
            value={searchDateFrom}
            onChange={(e) => setSearchDateFrom(e.target.value)}
            allowClear
          />
          <Input
            placeholder="结束日期 (YYYY-MM-DD)"
            style={{ width: 170 }}
            value={searchDateTo}
            onChange={(e) => setSearchDateTo(e.target.value)}
            allowClear
          />
        </div>

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
  );

  const renderDocumentsTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Collection selector and filters */}
      <Card
        style={{
          borderRadius: 8,
          border: '1px solid #e8eaf0',
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div
            style={{
              display: 'flex',
              gap: 12,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <Select
              placeholder="选择知识库"
              style={{ width: 220 }}
              options={collectionOptions}
              value={docCollection}
              onChange={(value) => {
                setDocCollection(value as string | undefined);
                setDocPagination({ current: 1, pageSize: 10, total: 0 });
                setSelectedDocIds([]);
              }}
              allowClear
              notFoundContent="暂无知识库，请先创建"
            />
            <Input
              placeholder="搜索文件名..."
              style={{ width: 200 }}
              prefix={<SearchOutlined />}
              value={docSearchQuery}
              onChange={(e) => setDocSearchQuery(e.target.value)}
              onPressEnter={() => fetchDocuments(1, docPagination.pageSize)}
              allowClear
            />
            <Select
              placeholder="文档类型"
              style={{ width: 130 }}
              options={DOCUMENT_TYPES}
              value={docTypeFilter}
              onChange={(value) => {
                setDocTypeFilter(value as string | undefined);
                setDocPagination({ current: 1, pageSize: 10, total: 0 });
              }}
              allowClear
            />
            <Input
              placeholder="开始日期"
              style={{ width: 150 }}
              value={docDateFrom}
              onChange={(e) => setDocDateFrom(e.target.value)}
              allowClear
            />
            <Input
              placeholder="结束日期"
              style={{ width: 150 }}
              value={docDateTo}
              onChange={(e) => setDocDateTo(e.target.value)}
              allowClear
            />
            <Button onClick={() => fetchDocuments(1, docPagination.pageSize)}>
              筛选
            </Button>
          </div>
        </Space>
      </Card>

      {/* Upload area */}
      <Collapse
        ghost
        items={[
          {
            key: 'upload',
            label: <Text strong>上传文档</Text>,
            children: (
              <Card
                style={{
                  borderRadius: 8,
                  border: '1px solid #e8eaf0',
                  marginTop: 8,
                }}
              >
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <div>
                    <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 14 }}>
                      选择目标知识库
                    </Text>
                    <Select
                      placeholder="选择知识库"
                      style={{ width: 300 }}
                      options={collectionOptions}
                      value={uploadCollection}
                      onChange={handleUploadCollectionChange}
                      allowClear
                      notFoundContent="暂无知识库，请先创建"
                    />
                  </div>

                  <div>
                    <Dragger
                      name="file"
                      multiple={false}
                      accept=".txt,.md,.pdf,.docx"
                      showUploadList={false}
                      beforeUpload={(file) => {
                        setSelectedFile(file);
                        return false;
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

                  {uploading && (
                    <div>
                      <Text style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                        正在处理文档（解析 → 分块 → 向量化 → 存储）...
                      </Text>
                      <Progress percent={uploadProgress} status="active" />
                    </div>
                  )}

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

                  {uploadedDocs.length > 0 && (
                    <>
                      <Divider style={{ margin: '8px 0' }} />
                      <div>
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: 12,
                          }}
                        >
                          <Text strong style={{ fontSize: 14 }}>
                            当前会话已上传
                          </Text>
                        </div>
                        <Table
                          dataSource={uploadedDocs}
                          columns={uploadDocColumns}
                          rowKey="id"
                          pagination={false}
                          size="small"
                        />
                      </div>
                    </>
                  )}
                </Space>
              </Card>
            ),
          },
        ]}
      />

      {/* Documents table */}
      {docCollection ? (
        <>
          {/* Batch operations bar */}
          {selectedDocIds.length > 0 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 16px',
                background: '#e6f7ff',
                border: '1px solid #91d5ff',
                borderRadius: 8,
              }}
            >
              <Text>
                已选择 <Text strong>{selectedDocIds.length}</Text> 个文档
              </Text>
              <Popconfirm
                title="批量删除"
                description={`确定要删除选中的 ${selectedDocIds.length} 个文档吗？`}
                onConfirm={handleBatchDelete}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  loading={batchDeleting}
                  size="small"
                >
                  批量删除
                </Button>
              </Popconfirm>
            </div>
          )}

          <Spin spinning={documentsLoading}>
            {documentsError && (
              <Alert
                message={documentsError}
                type="error"
                showIcon
                style={{ marginBottom: 16 }}
                closable
                onClose={() => setDocumentsError(null)}
              />
            )}

            {!documentsLoading && documents.length === 0 ? (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: '60px 24px',
                  background: '#fff',
                  borderRadius: 8,
                  border: '1px solid #e8eaf0',
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 32,
                    background: '#f0f2ff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 16,
                  }}
                >
                  <FileTextOutlined style={{ fontSize: 28, color: '#4f6ef7' }} />
                </div>
                <Text type="secondary" style={{ fontSize: 15, marginBottom: 8 }}>
                  暂无文档
                </Text>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  展开上方「上传文档」区域上传文件
                </Text>
              </div>
            ) : (
              <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e8eaf0' }}>
                <Table
                  rowKey="id"
                  dataSource={documents}
                  columns={docColumns}
                  pagination={{
                    current: docPagination.current,
                    pageSize: docPagination.pageSize,
                    total: docPagination.total,
                    pageSizeOptions: PAGE_SIZE_OPTIONS,
                    showSizeChanger: true,
                    showTotal: (total) => `共 ${total} 个文档`,
                    onChange: (page, pageSize) => {
                      setDocPagination((prev) => ({ ...prev, current: page, pageSize }));
                      fetchDocuments(page, pageSize);
                    },
                  }}
                  rowSelection={{
                    selectedRowKeys: selectedDocIds,
                    onChange: (keys) => setSelectedDocIds(keys),
                  }}
                  onRow={(record) => ({
                    style: { cursor: 'pointer' },
                    onDoubleClick: () => handlePreview(record),
                  })}
                  size="middle"
                  scroll={{ x: 600 }}
                />
              </div>
            )}
          </Spin>
        </>
      ) : (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
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
            请先选择一个知识库
          </Text>
        </div>
      )}
    </div>
  );

  // ── Render ───────────────────────────────────────────────────────────────

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
            children: renderCollectionsTab(),
          },
          {
            key: 'search',
            label: '搜索',
            children: renderSearchTab(),
          },
          {
            key: 'documents',
            label: '文档管理',
            children: renderDocumentsTab(),
          },
        ]}
      />

      {/* Create Collection Modal */}
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

      {/* Document Preview Modal */}
      <Modal
        title={
          <Space>
            <FileTextOutlined />
            <span>{previewDoc?.filename || '文档预览'}</span>
            {previewDoc?.type && <Tag>{previewDoc.type.toUpperCase()}</Tag>}
          </Space>
        }
        open={previewOpen}
        onCancel={() => {
          setPreviewOpen(false);
          setPreviewDoc(null);
        }}
        footer={[
          <Button key="close" onClick={() => {
            setPreviewOpen(false);
            setPreviewDoc(null);
          }}>
            关闭
          </Button>,
        ]}
        width={640}
        destroyOnClose
      >
        <Spin spinning={previewLoading}>
          {previewDoc && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Metadata */}
              <Row gutter={[16, 8]}>
                <Col span={12}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>文档 ID</Text>
                  <Text style={{ fontSize: 13 }}>{previewDoc.id}</Text>
                </Col>
                <Col span={12}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>所属知识库</Text>
                  <Text style={{ fontSize: 13 }}>{previewDoc.collection}</Text>
                </Col>
                <Col span={8}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>类型</Text>
                  <Text style={{ fontSize: 13 }}>{previewDoc.type?.toUpperCase() || '-'}</Text>
                </Col>
                <Col span={8}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>大小</Text>
                  <Text style={{ fontSize: 13 }}>{formatFileSize(previewDoc.size)}</Text>
                </Col>
                <Col span={8}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>Chunks</Text>
                  <Text style={{ fontSize: 13 }}>{previewDoc.chunks ?? '-'}</Text>
                </Col>
                <Col span={12}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>上传时间</Text>
                  <Text style={{ fontSize: 13 }}>{formatDate(previewDoc.uploaded_at)}</Text>
                </Col>
              </Row>

              <Divider style={{ margin: '8px 0' }} />

              {/* Content preview */}
              <div>
                <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>
                  内容预览
                </Text>
                {previewDoc.content ? (
                  <div
                    style={{
                      background: '#f8f9fc',
                      border: '1px solid #e8eaf0',
                      borderRadius: 8,
                      padding: 16,
                      maxHeight: 400,
                      overflow: 'auto',
                      fontSize: 13,
                      lineHeight: 1.6,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {previewDoc.content}
                  </div>
                ) : (
                  <Text type="secondary">暂无预览内容</Text>
                )}
              </div>
            </div>
          )}
        </Spin>
      </Modal>
    </div>
  );
}
