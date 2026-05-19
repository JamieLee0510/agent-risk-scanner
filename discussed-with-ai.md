


一句話

AI agent security 解決的不是 AI 幻覺問題，而是AI有幻覺之後會不會替你動手。
現在的AI agent 可以讀email、點擊網頁、調用API、寫程式碼、轉帳、訂票、刪除文件、發訊息等等。一旦agent 被惡意文字給挾持了，就可能拿著你的權限題攻擊者做事。


當前的科學理解：AI agent security 的正式問題是什麼？

我們先要了解，AI agent 比 LLM多了什麼風險？LLM 本身的風險包括幻覺（hallucination）、偏見（bias）、隱私洩漏（privacy leakage）、越獄（jailbreak）等等。但 AI agent 多了三個東西
- 工具使用（tool use）。它能調動搜索、瀏覽器、email、數據庫、shell、企業系統、支付接口等等
- 自主規劃（autonomous planning），agent 可以把目標拆成多步行動。
- 環境交互（environment interaction）。他會讀取網頁、email、PDF、程式碼庫、CRM紀錄等外部內容，而這些內容可能是攻擊者寫的


安全角度

- Prompt Injection
- Confused Deputy （混淆代理問題）
	- 一個有權限的agent被攻擊者誘導，用自己的高權限去替攻擊者完成壞事
AI agent security = LLM 安全 + 应用安全 + 身份权限管理 + 人机协作治理。



AI 給的整理

```
一个公司采购 agent，常问：模型准确率多少？能省多少人力？
更应该问：

它能访问哪些数据？
能调用哪些工具？
默认能不能写入？
谁批准高风险动作？
日志是否可审计？
出错能不能回滚？
供应商是否保留数据？
是否支持权限最小化（least privilege）？
```
·
```
一个简化安全框架：给 AI agent 上“五道锁”
身份锁（Identity）：agent 必须有独立身份，不要直接冒充用户。
权限锁（Permission）：最小权限，默认只读，高风险写入需批准。
环境锁（Sandbox）：浏览器、代码、文件系统、网络访问要隔离。
动作锁（Action Gate）：付款、删除、外发、改权限、运行代码必须确认。
审计锁（Audit）：记录 agent 看了什么、调用了什么、改了什么、为什么改。
```



```
未來比較可信的 agent 安全架構會長這樣：

模型層：更會識別惡意上下文。
工具層：每個工具都有最小權限和參數檢查。
策略層：高風險動作由 policy engine 決定，不由模型決定。
沙箱層：coding agent、browser agent、MCP server 隔離運行。
審計層：記錄 agent 看了什麼、信了什麼、做了什麼。
評測層：用 AgentDojo 類 benchmark 和企業自有紅隊持續測。
治理層：映射到 OWASP / NIST / CoSAI / CSA 框架。
```

爭議點


prompt injection 能不能被徹底解決

- 也許可以---透過模型訓練、輸入分類、上下文分離、工具沙箱來逐步降低風險
- 無法---只要模型必須讀不可信的自然語言，同時又能執行動作，就永遠存在「把數據誤當指令」的結構性風險


應該靠模型防禦、還是靠系統架構防禦？

- 模型防禦派會做分類器、拒絕策略、訓練資料、紅隊微調、RL-based attacker/defender
- 系統架構派則主張：模型可以幫忙，但不能是最後安全邊界；真正的安全要考 sandbox、least privilege、capability control、tool mediation、human approval

Browser agent 到底該不該存在？

OpenAI、Anthropic、Google 都在推 browser-use 或 computer-use 類 agent，因為這是 AI 真正進入工作流的入口。OpenAI 在 Atlas 安全文章裡說，agent mode 可以在同一個瀏覽器空間、上下文和資料中直接幫使用者處理日常工作流，但也使它成為 prompt injection 的高價值目標。
反對派或謹慎派會說：瀏覽器是最髒的環境，裡面有廣告、評論、hidden text、第三方腳本、釣魚頁、惡意 PDF；讓 agent 帶著登入態在裡面自主操作，本質上就是把一個容易受語言操縱的代理放進敵占區。


總結表格

人物 / 組織
江湖位置
核心思想
此刻關心什麼
Simon Willison
prompt injection 的命名者與公共思想家
prompt injection 是未解的結構性問題，不要迷信 prompt 防禦
持續追蹤新攻擊、新論文、新 agent 風險
Riley Goodside
早期 prompt injection 實驗者
用簡單語句就能讓模型違背原指令
模型行為、prompt 攻防、AI 產品漏洞
Kai Greshake / Sahar Abdelnabi / Thorsten Holz / Mario Fritz
indirect prompt injection 學術奠基者
LLM 應用模糊資料和指令；外部內容可遠端劫持 agent
IPI 分類、真實應用攻擊、資料竊取、蠕蟲式傳播
Florian Tramèr / Edoardo Debenedetti 等
安全評測與 adversarial ML 派
沒有嚴格 benchmark，就沒有可信安全聲稱
AgentDojo、CaMeL、可驗證防禦、adaptive attacks
OpenAI security teams
產品化 agent 的話語權中心
大規模紅隊、快速補洞、agent alignment with user intent
ChatGPT Atlas、browser agent prompt injection、自動化紅隊
Anthropic security / safety teams
安全敘事最強的大模型公司之一
承認 no browser agent is immune，重視 misuse 和 agentic cyber risk
Claude browser-use、MCP、安全評估、濫用偵測
Google SAIF / Google Security
框架化與生態安全派
把 AI 安全納入安全工程全流程
SAIF、Gemini 防禦、web 上的 IPI 野外監測
Microsoft Security / Semantic Kernel / PyRIT
企業 agent 與紅隊工具派
agent 風險要進入企業安全開發生命週期
AI Red Teaming Agent、Semantic Kernel、RCE 類 agent 漏洞
OWASP GenAI Security Project
風險分類與實務標準派
把攻防經驗整理成 Top 10
LLM Top 10、Agentic Applications Top 10、Agentic Skills Top 10
NIST
政府與企業治理派
AI 風險要可治理、可度量、可問責
AI RMF、GenAI Profile、critical infrastructure AI profile
Palo Alto Unit 42 / Google Threat Intelligence / Varonis / Invariant / OX
實戰情報與漏洞披露派
看真實攻擊、真實漏洞、真實供應鏈風險
野外 IPI、MCP、工具投毒、企業 Copilot 類漏洞


總結江湖

Simon Willison 這些人負責敲鐘：火已經燒起來了。
Greshake / Tramèr 這些人負責畫火勢圖：火從哪裡來，往哪裡燒。
OpenAI / Anthropic / Google / Microsoft 負責一邊蓋樓一邊裝消防。
OWASP / NIST / CoSAI 負責寫消防規範。
Unit 42 / Invariant / Varonis / OX 這些紅隊負責證明：你以為裝好了，其實窗戶還開著。

Ref

- https://chatgpt.com/share/6a058eda-52a0-83ec-95f2-00298d6ab72f
