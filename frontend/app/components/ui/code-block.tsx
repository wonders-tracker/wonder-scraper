import { Highlight, themes } from 'prism-react-renderer'

type CodeBlockProps = {
  code: string
  language?: 'bash' | 'json' | 'typescript' | 'javascript'
  className?: string
}

export function CodeBlock({ code, language = 'bash', className = '' }: CodeBlockProps) {
  return (
    <Highlight theme={themes.nightOwl} code={code.trim()} language={language}>
      {({ style, tokens, getLineProps, getTokenProps }) => (
        <pre
          className={`bg-zinc-900 rounded-lg p-4 font-mono text-sm overflow-x-auto ${className}`}
          style={{ ...style, background: 'rgb(24 24 27)' }}
        >
          {tokens.map((line, i) => (
            <div key={i} {...getLineProps({ line })}>
              {line.map((token, key) => (
                <span key={key} {...getTokenProps({ token })} />
              ))}
            </div>
          ))}
        </pre>
      )}
    </Highlight>
  )
}

export default CodeBlock
