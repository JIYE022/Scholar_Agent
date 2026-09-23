import { deviceState } from '@/store/device'
import {
  BookOutlined,
  FileSearchOutlined,
  FormOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import { Background } from './background'
import { Footer } from './footer'
import './index.scss'
import { Nav } from './nav'

export function BaseLayout({ children }: { children?: React.ReactNode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const device = useSnapshot(deviceState)

  return (
    <div className="base-layout">
      <div className="base-layout__sidebar">
        <div className="base-layout__logo">
          <button
            className="logo"
            onClick={() => (device.chatting ? null : navigate('/'))}
            aria-label="返回新对话"
          >
            <FileSearchOutlined />
          </button>
          <div className="brand-copy">
            <span className="title">Scholar Agent</span>
            <span className="subtitle">知识问答系统</span>
          </div>
        </div>

        <div className="base-layout__sidebar-main scrollbar-style">
          <div className="base-layout__sidebar-main-content">
            <div
              className="base-layout__nav-header"
              onClick={() => (device.chatting ? null : navigate('/'))}
            >
              <FormOutlined className="base-layout__nav-header-icon" />
              <span className="base-layout__nav-header-title">新对话</span>
            </div>

            <div className="base-layout__section-title">工作台</div>

            <div
              className={`base-layout__menu-item ${location.pathname.startsWith('/chat') ? 'is-active' : ''}`}
              onClick={() => (device.chatting ? null : navigate('/'))}
            >
              <MessageOutlined />
              <span>知识问答</span>
            </div>

            <Nav />

            <div
              className={`base-layout__menu-item ${location.pathname.startsWith('/repository') ? 'is-active' : ''}`}
              onClick={() => (device.chatting ? null : navigate('/repository'))}
            >
              <BookOutlined />
              <span>知识库管理</span>
            </div>
          </div>

          <Footer />
        </div>
      </div>

      <div className="base-layout__content">{children}</div>

      <Background />
    </div>
  )
}
