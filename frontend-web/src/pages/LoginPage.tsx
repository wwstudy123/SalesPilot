import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../lib/api/customers'
import './pages.css'

export function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('zhangsan')
  const [password, setPassword] = useState('pass123')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  const handleSubmit = async () => {
    setPending(true)
    setError(null)
    try {
      await login(username.trim(), password)
      navigate('/customers')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className='login-page'>
      <section className='panel login-page__card'>
        <h2>员工登录</h2>
        <p className='login-page__hint'>种子账号：zhangsan / lisi（pass123）、admin（admin123）</p>
        <input
          className='text-input'
          placeholder='用户名'
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <input
          className='text-input'
          type='password'
          placeholder='密码'
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {error ? <p className='login-page__error'>{error}</p> : null}
        <button type='button' className='primary-button' onClick={handleSubmit} disabled={pending}>
          登录
        </button>
      </section>
    </div>
  )
}
