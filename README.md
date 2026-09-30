# Scholar Agent

> Scholar Agent 是一个面向研究生和科研工作者的智能文献工作台。

> 它支持从 OpenAlex、arXiv 检索论文，将本地论文构建为个人知识库，并基于论文原文进行带引用的问答和多论文对比，帮助用户更快完成文献调研。

<img width="600" height="338" alt="Video Project 3 (2)_edited" src="https://github.com/user-attachments/assets/7e4fab6e-2ddc-47a2-898d-a4d436574b3a" />


## 核心能力

- 🔍 从 OpenAlex、arXiv 智能检索论文
- 📚 管理论文元数据、标签和阅读状态
- 💬 基于个人知识库进行检索增强问答
- 📑 对 2～5 篇论文进行多维度对比
- 🔗 回溯答案对应的原文片段和引用证据

## 为什么使用 Scholar Agent？

科研文献通常分散在多个平台中。找到论文后，研究者还需要手动整理、阅读、摘录和横向比较。普通大模型虽然可以总结内容，但回答经常缺少可核验的原文证据。

Scholar Agent 将论文检索、知识库管理、证据化问答和多论文对比整合在同一套工作流中，并尽可能让生成结论能够回溯到论文原文。

## 技术亮点
- 基于章节和句子边界的论文切块策略
- Elasticsearch 文本检索与模型重排，提高专业术语及复杂问题的召回效果。
- 通过prompt约束答案基于原文生成，支持原文片段溯源和知识不足拒答
- 论文对比采用多论文、逐维度的证据检索，先按论文、按维度检索证据，再生成对比结果
- 外部论文检索采用OpenAlex 与 arXiv 并行检索、归一化及去重

## 快速开始

### 启动后端

```powershell
cd backend
docker compose up -d --build
```

### 启动前端

```powershell
cd frontend
npm install
npm run dev
```
前端默认地址：http://localhost:5181/
后端 API 文档：http://localhost:8000/docs
