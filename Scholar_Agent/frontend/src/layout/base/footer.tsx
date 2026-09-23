import { userActions, userState } from '@/store/user'
import { LogoutOutlined } from '@ant-design/icons'
import { Avatar, Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useSnapshot } from 'valtio'
import './footer.scss'

export function Footer() {
  const user = useSnapshot(userState)
  const navigate = useNavigate()

  const logout = () => {
    userActions.logout()
    navigate('/login')
  }

  return (
    <div className="base-layout-footer">
      <div className="base-layout-footer__main">
        <div className="header">
          <Avatar className="avatar" size={42}>
            {user.username?.slice(0, 1).toUpperCase()}
          </Avatar>
          <div className="username">{user.username}</div>
        </div>
        <Button
          type="text"
          className="logout"
          icon={<LogoutOutlined />}
          onClick={logout}
        >
          退出登录
        </Button>
      </div>
    </div>
  )
}
