import * as api from '@/api'
import IconUpload from '@/assets/repository/upload.svg'
import {
  Form,
  Input,
  InputNumber,
  Select,
  Upload,
  UploadFile,
  UploadProps,
} from 'antd'
import { forwardRef, useImperativeHandle, useState } from 'react'
import styles from './upload.module.scss'

export type RepositoryUploadRef = {
  submit: () => Promise<void>
}

const readStatusOptions = [
  { label: '未读', value: 'unread' },
  { label: '阅读中', value: 'reading' },
  { label: '已读', value: 'read' },
  { label: '已归档', value: 'archived' },
]

export default forwardRef<RepositoryUploadRef, UploadProps>(
  function RepositoryUpload(props, ref) {
    const [form] = Form.useForm<API.PaperMetadata>()
    const [fileList, setFileList] = useState<UploadFile[]>([])

    useImperativeHandle(ref, () => ({
      submit: async () => {
        const file = fileList[0]
        if (!file?.originFileObj) {
          throw new Error('请选择要上传的论文文件')
        }
        if ((file.size ?? 0) > 5 * 1024 * 1024) {
          throw new Error('文件大小不能超过 5MB')
        }

        const metadata = await form.validateFields()
        setFileList((prev) =>
          prev.map((item) => ({ ...item, status: 'uploading' })),
        )

        try {
          await api.repository.upload({
            file: file.originFileObj as File,
            metadata,
          })
          setFileList((prev) =>
            prev.map((item) => ({ ...item, status: 'done' })),
          )
          window.$app.message.success('论文上传并解析完成')
        } catch (error: any) {
          setFileList((prev) =>
            prev.map((item) => ({
              ...item,
              status: 'error',
              response: error?.message,
            })),
          )
          throw error
        }
      },
    }))

    return (
      <div className={styles['repository-upload']}>
        <Upload.Dragger
          {...props}
          accept=".pdf,.doc,.docx,.txt"
          maxCount={1}
          fileList={fileList}
          onChange={(info) => {
            const nextList = info.fileList.slice(-1)
            setFileList(nextList)
            const selected = nextList[0]
            if (selected && !form.getFieldValue('title')) {
              form.setFieldValue(
                'title',
                selected.name.replace(/\.[^.]+$/, ''),
              )
            }
          }}
        >
          <img src={IconUpload} />
          <p className="ant-upload-text">
            拖拽论文到此，或 <span>点击选择</span>
          </p>
          <p className="ant-upload-hint">单个文件不超过 5MB</p>
        </Upload.Dragger>

        <Form<API.PaperMetadata>
          form={form}
          layout="vertical"
          initialValues={{
            authors: [],
            keywords: [],
            read_status: 'unread',
            personal_tags: [],
          }}
          className={styles['metadata-form']}
        >
          <Form.Item
            label="论文标题"
            name="title"
            rules={[{ required: true, message: '请输入论文标题' }]}
          >
            <Input maxLength={500} placeholder="上传文件后会自动使用文件名，可修改" />
          </Form.Item>
          <Form.Item label="作者" name="authors">
            <Select mode="tags" tokenSeparators={[',', '，']} placeholder="输入作者后按回车" />
          </Form.Item>
          <div className={styles['form-row']}>
            <Form.Item label="发表年份" name="year">
              <InputNumber min={1000} max={9999} placeholder="例如 2025" />
            </Form.Item>
            <Form.Item label="期刊 / 会议" name="venue">
              <Input placeholder="例如 ACL、Nature" />
            </Form.Item>
          </div>
          <Form.Item label="DOI" name="doi">
            <Input placeholder="例如 10.1145/xxxx.xxxx" />
          </Form.Item>
          <Form.Item label="关键词" name="keywords">
            <Select mode="tags" tokenSeparators={[',', '，']} placeholder="输入关键词后按回车" />
          </Form.Item>
          <Form.Item label="摘要" name="abstract">
            <Input.TextArea rows={3} placeholder="输入论文摘要" />
          </Form.Item>
          <div className={styles['form-row']}>
            <Form.Item label="研究主题" name="research_topic">
              <Input placeholder="例如 检索增强生成" />
            </Form.Item>
            <Form.Item label="阅读状态" name="read_status">
              <Select options={readStatusOptions} />
            </Form.Item>
          </div>
          <Form.Item label="个人标签" name="personal_tags">
            <Select mode="tags" tokenSeparators={[',', '，']} placeholder="例如 毕业论文重点" />
          </Form.Item>
        </Form>
      </div>
    )
  },
)
