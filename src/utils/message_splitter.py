import asyncio
from src.config import MAX_MESSAGE_LENGTH
from telethon.errors import FloodWaitError

async def send_long_message(event, text: str, prefix: str = ""):
    """
    Split and send long messages
    
    Args:
        event: Telegram event
        text: Text to send
        prefix: Optional prefix for continuation messages (e.g., "Part 2:")
    """
    # Calculate max chunk size considering prefix for continuation messages
    prefix_length = len(prefix) if prefix else 0
    max_chunk_size = MAX_MESSAGE_LENGTH - prefix_length if prefix else MAX_MESSAGE_LENGTH
    
    if len(text) <= MAX_MESSAGE_LENGTH:
        await event.reply(text)
        return
    
    # Split by paragraphs first
    chunks = []
    current_chunk = ""
    
    for paragraph in text.split('\n\n'):
        if len(current_chunk) + len(paragraph) + 2 <= max_chunk_size:
            current_chunk += paragraph + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + '\n\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # If still too long, split by sentences
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chunk_size:
            final_chunks.append(chunk)
        else:
            # Split by sentences
            sentences = chunk.split('. ')
            temp = ""
            for sentence in sentences:
                if len(temp) + len(sentence) + 2 <= max_chunk_size:
                    temp += sentence + '. '
                else:
                    if temp:
                        final_chunks.append(temp.strip())
                    temp = sentence + '. '
            if temp:
                final_chunks.append(temp.strip())
    
    # Send chunks
    for i, chunk in enumerate(final_chunks):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if i == 0:
                    await event.reply(chunk)
                    await asyncio.sleep(2.0)  # Delay after first message too
                else:
                    # Add prefix to continuation messages if provided
                    message_to_send = f"{prefix}{chunk}" if prefix else chunk
                    
                    # Double check message length before sending
                    if len(message_to_send) > MAX_MESSAGE_LENGTH:
                        # If still too long, split the chunk further by newlines
                        lines = chunk.split('\n')
                        temp_msg = ""
                        for line in lines:
                            test_msg = f"{prefix}{temp_msg}\n{line}" if temp_msg else f"{prefix}{line}"
                            if len(test_msg) <= MAX_MESSAGE_LENGTH:
                                temp_msg = f"{temp_msg}\n{line}" if temp_msg else line
                            else:
                                if temp_msg:
                                    await event.respond(f"{prefix}{temp_msg}")
                                    await asyncio.sleep(2.0)
                                temp_msg = line
                        if temp_msg:
                            await event.respond(f"{prefix}{temp_msg}")
                            await asyncio.sleep(2.0)
                    else:
                        await event.respond(message_to_send)
                        await asyncio.sleep(2.0)
                
                # Success, break retry loop
                break
                        
            except FloodWaitError as e:
                # Telegram is rate limiting, wait the required time
                wait_time = e.seconds
                retry_count += 1
                
                print(f"⚠️ FloodWait: Waiting {wait_time} seconds (retry {retry_count}/{max_retries})...")
                
                # Only notify user on first retry
                if retry_count == 1:
                    try:
                        await event.respond(f"⏳ Telegram rate limit - waiting {wait_time}s...")
                    except:
                        pass  # If we can't send notification, just wait
                
                await asyncio.sleep(wait_time + 1)  # Wait required time + 1 second buffer
                
                if retry_count >= max_retries:
                    print(f"❌ Failed to send message after {max_retries} retries")
                    try:
                        await event.respond("❌ Failed to send message due to rate limits. Please try again later.")
                    except:
                        pass
                    break

