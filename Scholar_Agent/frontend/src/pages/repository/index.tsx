import * as api from '@/api'
import IconDelete from '@/assets/repository/action/delete.svg'
import IconEdit from '@/assets/repository/action/edit.svg'
import IconSearch from '@/assets/repository/search.svg'
import { PlusOutlined } from '@ant-design/icons'
import { useRequest } from 'ahooks'
import {
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
} from 'antd'
import { ColumnsType } from 'antd/es/table'
import { TableRowSelection } from 'antd/es/table/interface'
import dayjs from 'dayjs'
import { useMemo, useRef, useState } from 'react'
import { FileIcon } from './components/file-icon'
import RepositoryUpload, { RepositoryUploadRef } from './components/upload'
import styles from './index.module.scss'

const readStatus = {
  unread: { label: '未读', color: 'default' },
  reading: { label: '阅读中', color: 'processing' },
  read: { label: '已读', color: 'success' },
  archived: { label: '已归档', color: 'warning' },
} as const

const readStatusOptions = Object.entries(readStatus).map(([value, config]) => ({
  value,
  label: config.label,
}))

export default function Index() {
  const [keyword, setKeyword] = useState('')
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [openUpload, setOpenUpload] = useState(false)
  const [uploading, setUploading] = useState(false)
  const uploadRef = useRef<RepositoryUploadRef>(null)

  const [editingPaper, setEditingPaper] = useState<API.Paper | null>(null)
  const [saving, setSaving] = useState(false)
  const [editForm] = Form.useForm<API.PaperMetadata>()

  const { data = [], refresh } = useRequest(async () => {
    const { data } = await api.repository.list()
    return data ?? []
  })

  const filteredData = useMemo(() => {
    const normalized = keyword.trim().toLowerCase()
    if (!normalized) return data
    return data.filter((paper) =>
      [
        paper.title,
        paper.file_name,
        paper.venue,
        paper.doi,
        paper.research_topic,
        ...paper.authors,
        ...paper.keywords,
        ...paper.personal_tags,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized)),
    )
  }, [data, keyword])

  const openEdit = (paper: API.Paper) => {
    setEditingPaper(paper)
    editForm.setFieldsValue({
      title: paper.title ?? '',
      authors: paper.authors,
      year: paper.year,
      venue: paper.venue,
      doi: paper.doi,
      keywords: paper.keywords,
      abstract: paper.abstract,
      research_topic: paper.research_topic,
      read_status: paper.read_status,
      personal_tags: paper.personal_tags,
    })
  }

  const columns = useMemo<ColumnsType<API.Paper>>(
    () => [
      {
        title: '论文标题',
        dataIndex: 'title',
        width: 260,
        render(value: string, row) {
          const suffix = row.file_name.split('.').pop() as FileIcon
          return (
            <Tooltip title={`文件：${row.file_name}`}>
              <button
                type="button"
                className={styles['repository-page__paper-title']}
                onClick={() => openEdit(row)}
              >
                <FileIcon className={styles['icon']} suffix={suffix} />
                {value || row.file_name}
              </button>
            </Tooltip>
          )
        },
      },
      {
        dataIndex: 'chunk_count',
        title: 'Chunk 数量',
        width: 110,
        align: 'center',
        render: (value: number | undefined) => value ?? 0,
      },
      {
        title: '作者',
        dataIndex: 'authors',
        width: 180,
        ellipsis: true,
        render: (authors: string[]) => authors?.join('、') || '—',
      },
      {
        title: '年份',
        dataIndex: 'year',
        width: 80,
        render: (value) => value ?? '—',
      },
      {
        title: '期刊 / 会议',
        dataIndex: 'venue',
        width: 160,
        ellipsis: true,
        render: (value) => value || '—',
      },
      {
        title: '研究主题',
        dataIndex: 'research_topic',
        width: 150,
        ellipsis: true,
        render: (value) => value || '—',
      },
      {
        title: '阅读状态',
        dataIndex: 'read_status',
        width: 100,
        render(value: API.ReadStatus) {
          const config = readStatus[value]
          return <Tag color={config.color}>{config.label}</Tag>
        },
      },
      {
        title: '个人标签',
        dataIndex: 'personal_tags',
        width: 190,
        render(tags: string[]) {
          if (!tags?.length) return '—'
          return (
            <Space size={[0, 4]} wrap>
              {tags.slice(0, 3).map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
              {tags.length > 3 && <Tag>+{tags.length - 3}</Tag>}
            </Space>
          )
        },
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        width: 150,
        render: (value) => dayjs(value).format('YYYY-MM-DD HH:mm'),
      },
      {
        title: '操作',
        dataIndex: 'action',
        width: 100,
        fixed: 'right',
        render(_, row) {
          return (
            <Space>
              <Button
                type="text"
                shape="circle"
                size="small"
                title="编辑论文信息"
                onClick={() => openEdit(row)}
              >
                <img src={IconEdit} />
              </Button>
              <Popconfirm
                title="确定要删除这篇论文吗？"
                description="论文记录、文件和检索切片将一并删除。"
                onConfirm={async () => {
                  await api.repository.remove({ paper_id: row.id })
                  refresh()
                }}
              >
                <Button type="text" shape="circle" size="small">
                  <img src={IconDelete} />
                </Button>
              </Popconfirm>
            </Space>
          )
        },
      },
    ],
    [refresh],
  )

  const rowSelection: TableRowSelection<API.Paper> = {
    selectedRowKeys,
    onChange: setSelectedRowKeys,
  }

  return (
    <div className={styles['repository-page']}>
      <div className={styles['repository-page__header']}>
        <div className={styles['title']}>文献知识库</div>
        <div className={styles['desc']}>
          管理论文元数据、阅读状态和个人研究标签。
        </div>
      </div>

      <div className={styles['repository-page__body']}>
        <div className={styles['header']}>
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            allowClear
            placeholder="搜索标题、作者、主题或标签"
            prefix={<img src={IconSearch} />}
            style={{ width: 280 }}
          />
          <Button type="primary" onClick={() => setOpenUpload(true)}>
            <PlusOutlined />
            添加论文
          </Button>
        </div>

        <Table<API.Paper>
          rowKey="id"
          columns={columns}
          dataSource={filteredData}
          rowSelection={rowSelection}
          scroll={{ x: 1370 }}
          pagination={{ pageSize: 10, showSizeChanger: false }}
        />
      </div>

      <Modal
        title="上传论文"
        open={openUpload}
        width={720}
        destroyOnClose
        confirmLoading={uploading}
        onCancel={() => !uploading && setOpenUpload(false)}
        onOk={async () => {
          setUploading(true)
          try {
            await uploadRef.current?.submit()
            setOpenUpload(false)
            refresh()
          } catch (error: any) {
            window.$app.message.error(error?.message || '上传失败')
          } finally {
            setUploading(false)
          }
        }}
      >
        <RepositoryUpload beforeUpload={() => false} ref={uploadRef} />
      </Modal>

      <Modal
        title="编辑论文信息"
        open={Boolean(editingPaper)}
        width={720}
        destroyOnClose
        confirmLoading={saving}
        onCancel={() => setEditingPaper(null)}
        onOk={async () => {
          if (!editingPaper) return
          const changes = await editForm.validateFields()
          setSaving(true)
          try {
            await api.repository.update({ paper_id: editingPaper.id, changes })
            window.$app.message.success('论文信息已更新')
            setEditingPaper(null)
            refresh()
          } finally {
            setSaving(false)
          }
        }}
      >
        <Form<API.PaperMetadata> form={editForm} layout="vertical">
          <Form.Item label="论文标题" name="title" rules={[{ required: true }]}>
            <Input maxLength={500} />
          </Form.Item>
          <Form.Item label="作者" name="authors">
            <Select mode="tags" tokenSeparators={[',', '，']} />
          </Form.Item>
          <Space align="start" size="large">
            <Form.Item label="发表年份" name="year">
              <InputNumber min={1000} max={9999} />
            </Form.Item>
            <Form.Item label="期刊 / 会议" name="venue">
              <Input style={{ width: 260 }} />
            </Form.Item>
            <Form.Item label="阅读状态" name="read_status">
              <Select options={readStatusOptions} style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Form.Item label="DOI" name="doi">
            <Input />
          </Form.Item>
          <Form.Item label="关键词" name="keywords">
            <Select mode="tags" tokenSeparators={[',', '，']} />
          </Form.Item>
          <Form.Item label="摘要" name="abstract">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item label="研究主题" name="research_topic">
            <Input />
          </Form.Item>
          <Form.Item label="个人标签" name="personal_tags">
            <Select mode="tags" tokenSeparators={[',', '，']} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
