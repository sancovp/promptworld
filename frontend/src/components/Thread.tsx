import { Thread as AUIThread, makeMarkdownText } from "@assistant-ui/react-ui";
import { makePrismLightSyntaxHighlighter } from "@assistant-ui/react-syntax-highlighter";
import { PrismLight } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import jsx from "react-syntax-highlighter/dist/esm/languages/prism/jsx";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import tsx from "react-syntax-highlighter/dist/esm/languages/prism/tsx";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import markdown from "react-syntax-highlighter/dist/esm/languages/prism/markdown";
import css from "react-syntax-highlighter/dist/esm/languages/prism/css";
import yaml from "react-syntax-highlighter/dist/esm/languages/prism/yaml";
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import rust from "react-syntax-highlighter/dist/esm/languages/prism/rust";
import go from "react-syntax-highlighter/dist/esm/languages/prism/go";
import java from "react-syntax-highlighter/dist/esm/languages/prism/java";

// PREBUILT assistant-ui chat at FULL power — version-coherent 0.14 set:
//   @assistant-ui/react-ui (styled <Thread/> + makeMarkdownText) + @assistant-ui/react-markdown
//   + @assistant-ui/react-syntax-highlighter (Prism). makePrismLightSyntaxHighlighter wraps
//   react-syntax-highlighter's PrismLight singleton, so we register languages on it statically
//   (no runtime variable dynamic import — that one is unbundlable by vite and renders plain).
//   Result: code blocks render SYNTAX-HIGHLIGHTED (oneDark) in a styled panel; list/heading prose
//   bullets are restored in styles.css.
for (const [name, lang] of Object.entries({
  python, javascript, jsx, typescript, tsx, json, bash, markdown, css, yaml, sql, rust, go, java,
})) {
  PrismLight.registerLanguage(name, lang as any);
}

const SyntaxHighlighter = makePrismLightSyntaxHighlighter({ style: oneDark });
const MarkdownText = makeMarkdownText({ components: { SyntaxHighlighter } });

export function Thread({
  placeholder = "Message the engineer-CEO…",
  emptyText = "Talk to your engineer-CEO.",
}: {
  placeholder?: string;
  emptyText?: string;
} = {}) {
  return (
    <AUIThread
      welcome={{ message: emptyText }}
      assistantMessage={{ components: { Text: MarkdownText } }}
      strings={{ composer: { input: { placeholder } } }}
    />
  );
}
