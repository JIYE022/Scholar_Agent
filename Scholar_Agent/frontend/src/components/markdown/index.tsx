import classNames from 'classnames'
import { Marked, Renderer, TokenizerAndRendererExtension } from 'marked'
import { useMemo } from 'react'
import './index.scss'

export default function Markdown(props: {
  className?: string
  value?: string
  extensions?: TokenizerAndRendererExtension[]
  onClick?: React.MouseEventHandler<HTMLDivElement>
}) {
  const { value, extensions, className, ...otherProps } = props

  const html = useMemo(() => {
    const renderer = new Renderer()

    const marked = new Marked({
      extensions: props.extensions,
    })
    const html = marked.parse(props.value ?? '', {
      // Comparison answers use GitHub-flavoured Markdown tables. Disabling
      // GFM made the table source render as a single line of plain text.
      gfm: true,
      renderer,
    })

    return html
  }, [value, extensions])

  return (
    <div
      className={classNames('com-markdown', className)}
      {...otherProps}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
