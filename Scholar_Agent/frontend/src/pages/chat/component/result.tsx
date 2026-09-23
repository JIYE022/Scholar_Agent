import IconCopy from '@/assets/chat/copy.svg'
import IconRefresh from '@/assets/chat/refresh.svg'
import IconShare from '@/assets/chat/share.svg'
import IconTip from '@/assets/chat/tip.svg'
import Markdown from '@/components/markdown'
import { ArrowRightOutlined } from '@ant-design/icons'
import { Button, Card, Dropdown, Tag } from 'antd'
import classNames from 'classnames'
import dayjs from 'dayjs'
import { TokenizerAndRendererExtension } from 'marked'
import { useCallback, useMemo } from 'react'
import styles from './result.module.scss'

export function Result(props: {
  item: API.ChatItem
  isEnd?: boolean
  onSend?: (text: string) => void
  onRefrence?: (index: number) => void
}) {
  const { item, isEnd, onSend, onRefrence } = props

  const shareMenu = useMemo(() => {
    return [
      {
        key: 'pdf',
        label: '导出为 TXT',
        onClick: async () => {
          const url = `data:text/plain;charset=utf-8,${encodeURIComponent(item.content ?? '')}`
          const a = document.createElement('a')
          a.href = url
          a.download = 'output.txt'
          a.click()
        },
      },
      {
        key: 'email',
        label: '发送到 Email',
      },
    ]
  }, [item.content])

  /* markdown */
  const extensions = useMemo<TokenizerAndRendererExtension[]>(
    () => [
      {
        name: 'reference',
        level: 'inline',
        start(src) {
          return src.match(/\[(?:\d+)\]|##(?:\d+|#+)\$\$/)?.index
        },
        tokenizer(src) {
          // New answers use normal academic citations such as [1]. Keep the
          // legacy marker support so historical messages remain clickable.
          const match = /^(?:\[(\d+)\]|##(?:(\d+)|(#+))\$\$)/.exec(src)
          if (match) {
            const [raw, bracketIndex, legacyNumericIndex, hashIndex] = match
            const citationNumber = bracketIndex || legacyNumericIndex
              ? Number(bracketIndex || legacyNumericIndex)
              : hashIndex.length

            if (!Number.isSafeInteger(citationNumber) || citationNumber < 1) {
              return
            }

            return {
              type: 'reference',
              raw,
              citationNumber,
              tokens: [],
            }
          }
        },
        renderer(token) {
          const citationNumber = Number(token.citationNumber)
          const referenceIndex = citationNumber - 1
          return `<span class="refrence-token" data-refrence-index="${referenceIndex}">[${citationNumber}]</span>`
        },
      },
    ],
    [],
  )

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement
      const index = target.getAttribute('data-refrence-index')
      if (index) {
        onRefrence?.(Number(index))
      }
    },
    [onRefrence],
  )

  return (
    <div className={styles['chat-message-result']}>
      {item.think ? (
        <Markdown
          className={classNames(
            styles['chat-message-result__think'],
            styles['chat-message-result__md'],
          )}
          value={item.think}
          extensions={extensions}
          onClick={handleClick}
        />
      ) : null}

      {item.content ? (
        <Markdown
          className={styles['chat-message-result__md']}
          value={item.content}
          extensions={extensions}
          onClick={handleClick}
        />
      ) : null}

      {item.externalPapers?.length ? (
        <div className={styles['external-paper-list']}>
          {item.externalPapers.map((paper, index) => (
            <Card
              className={styles['external-paper-card']}
              key={paper.external_id}
              size="small"
              title={
                <span className={styles['external-paper-card__title']}>
                  {index + 1}. {paper.title}
                </span>
              }
              extra={paper.year ? <Tag color="blue">{paper.year}</Tag> : null}
            >
              <div className={styles['external-paper-card__meta']}>
                {paper.authors.slice(0, 5).join('、') || '作者未知'}
                {paper.authors.length > 5 ? ' 等' : ''}
              </div>
              <div className={styles['external-paper-card__tags']}>
                {paper.sources.map((source) => (
                  <Tag key={source}>{source}</Tag>
                ))}
                {paper.venue ? <Tag>{paper.venue}</Tag> : null}
                {paper.citation_count != null ? (
                  <Tag>引用 {paper.citation_count}</Tag>
                ) : null}
              </div>
              {paper.relevance_reason ? (
                <div className={styles['external-paper-card__reason']}>
                  <strong>推荐理由：</strong>{paper.relevance_reason}
                </div>
              ) : null}
              {paper.abstract ? (
                <div className={styles['external-paper-card__abstract']}>
                  {paper.abstract}
                </div>
              ) : null}
              <div className={styles['external-paper-card__links']}>
                <a href={paper.landing_url} target="_blank" rel="noreferrer">
                  查看详情
                </a>
                {paper.pdf_url ? (
                  <a href={paper.pdf_url} target="_blank" rel="noreferrer">
                    查看 PDF
                  </a>
                ) : null}
                {paper.doi ? <span>DOI: {paper.doi}</span> : null}
              </div>
            </Card>
          ))}
        </div>
      ) : null}

      {item.error ? (
        <div className={styles['chat-message-result__error']}>{item.error}</div>
      ) : null}

      {item.loading ? null : (
        <>
          <div className={styles['chat-message-result__actions']}>
            <div className={styles['date']}>
              {dayjs().format('HH:mm YYYY/MM/DD')}
            </div>

            {isEnd ? null : (
              <Button
                variant="text"
                color="primary"
                shape="circle"
                size="small"
                style={{ color: 'var(--ant-color-primary)' }}
              >
                <img src={IconRefresh} />
              </Button>
            )}

            <Button
              variant="text"
              color="primary"
              shape="circle"
              size="small"
              style={{ color: 'var(--ant-color-primary)' }}
            >
              <img src={IconTip} />
            </Button>

            <Button
              variant="text"
              color="primary"
              shape="circle"
              size="small"
              style={{ color: 'var(--ant-color-primary)' }}
            >
              <img src={IconCopy} />
            </Button>

            <Dropdown menu={{ items: shareMenu }}>
              <Button
                variant="text"
                color="primary"
                shape="circle"
                size="small"
                style={{ color: 'var(--ant-color-primary)' }}
              >
                <img src={IconShare} />
              </Button>
            </Dropdown>
          </div>

          {isEnd ? (
            <div className={styles['chat-message-result__quick-reply']}>
              {item.recommended_questions?.map((item) => (
                <Button
                  className={styles['item']}
                  key={item}
                  onClick={() => onSend?.(item)}
                >
                  <span className={styles['text']}>🔎 {item}</span>
                  <ArrowRightOutlined className={styles['arrow']} />
                </Button>
              ))}
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}
