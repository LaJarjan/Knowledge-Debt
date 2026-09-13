# Knowledge Debt — handoff-demo

先看懂这次改动中值得关注的行为，再决定如何维护。

比较基线: c71542dd219f78159073f8a4c0cf8b584c4455ef

目标版本: working-tree

源码快照: 65dc97e17778d88734142e1b528bbebd0dc3d63b4e7f2abc3e288b6644071f8b

基于 Git 与 Python AST 在本地生成，未调用模型，也未执行仓库代码。

当前仅支持 semaphore 构造、计数重试形态和 finally 清理。动态调用与跨文件依赖仍需人工确认。

## 发生变化的文件

- worker.py: 相对基线变化 (3 cards)

## 并发限制在何处创建和使用 — fetch\_batch

worker.py:7

相对基线变化 · 说明需要复核

### 为什么值得关注

一般性维护建议 · 不代表已确认的设计动机

只有共享并使用同一限制器的任务，才可能受它共同约束。修改并发上限前，需要确认构造位置、对象生命周期与使用范围。

### 源码直接支持的事实

- The function contains a call to asyncio.Semaphore. (worker.py:7)

```python
asyncio.Semaphore(4)
```

- Its initial value argument is 4. (worker.py:7)

```python
asyncio.Semaphore(4)
```

- The constructor expression is inside fetch\_batch, not at module scope. (worker.py:7)

```python
asyncio.Semaphore(4)
```

- No matching with/acquire/release syntax was identified in this function's direct body; nested functions and other methods are not followed for uses. (worker.py:7)

```python
asyncio.Semaphore(4)
```

### 目前还不能确定

The import resolves lexically to asyncio/threading. Matching expressions do not prove object identity or runtime control flow. A constructor call alone does not prove requests are guarded; nested closures, other methods and monkey-patching are not resolved.

### 基线版本的事实

- The function contains a call to asyncio.Semaphore. (L7)

- Its initial value argument is 2. (L7)

- The constructor expression is inside fetch\_batch, not at module scope. (L7)

- No matching with/acquire/release syntax was identified in this function's direct body; nested functions and other methods are not followed for uses. (L7)

### 上次指南中的事实

- The function contains a call to asyncio.Semaphore. (L7)

- Its initial value argument is 2. (L7)

- The constructor expression is inside fetch\_batch, not at module scope. (L7)

- No matching with/acquire/release syntax was identified in this function's direct body; nested functions and other methods are not followed for uses. (L7)

### 检查一下自己的理解

In fetch\_batch, where is this semaphore constructed and what initial value is supplied? Identify matching with/acquire/release syntax in this function's direct body. What remains unknown about uses outside that body?

阅读指南不会记录为已理解。需要记录回答时，请运行 kdebt drill 并自行核对事实。

已有自查记录: 尚未记录回答

## 失败之后，操作会如何重试 — retry\_read

worker.py:17

相对基线变化 · 说明需要复核

### 为什么值得关注

一般性维护建议 · 不代表已确认的设计动机

超时本身不能证明远端写入没有发生。扩大重试范围前，应确认操作能否安全重复，以及成功或失败后如何退出。

### 源码直接支持的事实

- The loop iterates over range(3). (worker.py:17)

```python
range(3)
```

- Delay-containing handlers catch TimeoutError. (worker.py:20)

```python
except TimeoutError:
    await asyncio.sleep(2 ** attempt)
```

- A handler contains the delay call asyncio.sleep(2 \*\* attempt). (worker.py:21)

```python
asyncio.sleep(2 ** attempt)
```

- The try body contains the exit return await client.get(key). (worker.py:19)

```python
return await client.get(key)
```

### 目前还不能确定

Counted retry-shaped syntax, not a control-flow proof. Iterations are not necessarily attempts; external effects and idempotency remain unverified.

### 基线版本的事实

- The loop iterates over range(2). (L17)

- Delay-containing handlers catch TimeoutError. (L20)

- A handler contains the delay call asyncio.sleep(2 \*\* attempt). (L21)

- The try body contains the exit return await client.get(key). (L19)

### 上次指南中的事实

- The loop iterates over range(2). (L17)

- Delay-containing handlers catch TimeoutError. (L20)

- A handler contains the delay call asyncio.sleep(2 \*\* attempt). (L21)

- The try body contains the exit return await client.get(key). (L19)

### 检查一下自己的理解

In retry\_read, identify the counted loop, the exceptions whose handlers contain a delay, the delay expression and the try-body exit. Does that alone prove the operation is safe to repeat?

阅读指南不会记录为已理解。需要记录回答时，请运行 kdebt drill 并自行核对事实。

已有自查记录: 尚未记录回答

## 资源清理是怎样安排的 — consume

worker.py:26

相对基线新增 · 上次之后新增

### 为什么值得关注

一般性维护建议 · 不代表已确认的设计动机

finally 中存在清理调用，不等于每条路径都能完成清理。需要进一步检查条件分支、前序异常与资源归属。

### 源码直接支持的事实

- This try statement has a finally suite. (worker.py:26)

```python
try:
    return connection.read()
finally:
    connection.close()
```

- That suite contains connection.close(). (worker.py:29)

```python
connection.close()
```

### 目前还不能确定

Containing a cleanup call does not prove that cleanup always completes. Conditions, earlier exceptions, cancellation and process exit matter.

### 检查一下自己的理解

In consume, identify the cleanup calls inside finally. Does their presence alone establish that cleanup completes on every exit?

阅读指南不会记录为已理解。需要记录回答时，请运行 kdebt drill 并自行核对事实。

已有自查记录: 尚未记录回答
