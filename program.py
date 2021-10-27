import sys
import time

binary_symbols = ['0', '1']
ascii_symbols = [chr(x) for x in range(256)] 

with open('canterbury-corpus-master/canterbury/alice29.txt') as f:
    mystring = f.read()

def bytes_to_binary(gen): #converts a stream of characters to a stream of binary
    for character in gen:
        bits = '{:0>8}'.format(format(character, 'b')) 
        for b in bits:
            yield b

def binary_to_bytes(bstr):
    return bytes(int(bstr[i : i + 8], 2) for i in range(0, len(bstr), 8))

def encodetopairs(gen,symbols): #given a stream and a list of potential symbols which can occur in the stream, returns pairs representing the encoded substrings
    table = [None] + symbols #value of None signifies end of stream, one final message pulled from different pool
    possibleoutputs = table[:]
    try:
        currentstr = next(gen)
        assert currentstr in symbols
    except StopIteration: #trying to encode the empty string is a weird case
        yield (table.index(None),len(table))
        yield (table.index(None),len(table))
        raise StopIteration
    for newcharacter in gen:
        assert newcharacter in symbols
        if (currentstr + newcharacter) in table:
            currentstr += newcharacter
        else:
            yield (possibleoutputs.index(currentstr),len(possibleoutputs))
            tableset = set(table) #for speed
            possibleoutputs = list(filter(lambda s: (s == None) or ((currentstr + s[0] not in tableset) and any((s + c not in tableset) for c in symbols)),table + [currentstr + newcharacter]))
            table.append(currentstr + newcharacter)
            currentstr = newcharacter
    #end of stream
    yield (possibleoutputs.index(None),len(possibleoutputs))
    possibleoutputs = table[:] #lazy, but proper logic would be complex and save at most 1 bit per file or so
    yield (possibleoutputs.index(currentstr),len(possibleoutputs))

def decodefromindexes(gen,symbols): #interactive function, passes expected possibilites back to index generating function
    table = [None] + symbols
    possibleinputs = table[:]
    inputlen = len(possibleinputs)
    previousknownportion = None
    for index in gen: #gen never ought to output less than twice
        assert index >= 0
        assert index < inputlen
        if index > 0:
            if index == inputlen - 1: 
                if inputlen == len(possibleinputs): #if previously recieved input was not possible
                    segment = possibleinputs[index]
                    table.append(previousknownportion + segment[0])
                else: #cScSc case
                    table.append(previousknownportion + previousknownportion[0])
                    segment = previousknownportion + previousknownportion[0]
            else:
                segment = possibleinputs[index]
                if previousknownportion != None: #true whenever not first run
                    table.append(previousknownportion + segment[0])
            for symbol in segment:
                yield symbol
            tableset = set(table)
            possibleinputs = list(filter(lambda s: (s == None) or ((segment + s[0] not in tableset) and any((s + c not in tableset) for c in symbols)),table))
            if segment + segment[0] not in table:
                inputlen = len(possibleinputs) + 1
            else:
                inputlen = len(possibleinputs)
            previousknownportion = segment
            gen.send(inputlen)
        else:
            possibleinputs = table[:] #as above, not worth improving
            inputlen = len(possibleinputs) + 1 #prev is assumed possible as well
            gen.send(inputlen)
            index = next(gen) #this should be the last output of gen
            assert index >= 0
            assert index < inputlen
            assert index > 0 or previousknownportion == None
            if index == 0:
                pass #empty string
            else:
                if index == inputlen - 1:
                    segment = previousknownportion + previousknownportion[0]
                else:
                    segment = possibleinputs[index]
                for symbol in segment:
                    yield symbol
            break

def pairstoindexesdirect(gen,symbols): #just for testing, not useful for actual encoding/decoding
    x = len(symbols) + 1
    for pair in gen:
        assert pair[1] == x
        x = yield pair[0]
        yield

def pairstobitstream(gen): 
    for pair in gen:
        bits = ('{:0>' + str((pair[1]-1).bit_length()) + '}').format(format(pair[0],'b'))
        for bit in bits:
            yield bit

def pairstobigintbits(gen): #not a generator, not possible to stream with
    x = 0
    multiplier = 1
    for pair in gen:
        x += pair[0] * multiplier
        multiplier *= pair[1]
    return format(x,'b')

def bitstreamtopairs(gen,symbols):
    x = len(symbols) + 1
    while True:
        s = ''
        for i in range((x-1).bit_length()):
            try:
                s += next(gen)
            except StopIteration:
                raise ValueError()
        x = yield int(s, 2)
        yield

def bigintbitstopairs(num,symbols):
    num = int(num,2)
    x = len(symbols) + 1
    while True:
        n = num % x
        num = num // x
        x = yield n
        yield

def padbitstring(s):
    s += '1'
    while len(s) % 8 != 0:
        s += '0'
    return s

def unpadbitstring(s):
    while s[-1] == '0':
        s = s[:-1]
    s = s[:-1]
    return s

def encode(source, target, info):
    with open(source, 'rb') as f:
        sourcetext = f.read()
    sourcetext = ''.join(chr(b) for b in sourcetext) #strings and bytes are different and I hate it 
    infostring = 'original filesize : ' + str(len(sourcetext)) + ' bytes\n'
    starttime = time.time_ns()
    pairstream = encodetopairs(iter(sourcetext),ascii_symbols)
    bits = pairstobigintbits(pairstream)
    padded = padbitstring(bits)
    towrite = binary_to_bytes(padded)
    stoptime = time.time_ns()
    infostring += 'final filesize : ' + str(len(towrite)) + ' bytes\n'
    infostring += 'compression ratio : ' + str(100*(1-(len(towrite)/len(sourcetext)))) + '%\n'
    infostring += 'compression time : ' + str((stoptime - starttime) // 1000000) + 'ms\n'
    #print(repr(towrite))
    with open(target, 'wb') as f2:
        f2.write(towrite)
    with open(info, 'w') as f3:
        f3.write(infostring)

def decode(source, target, info):
    with open(source, 'rb') as f:
        sourcetext = f.read()
    starttime = time.time_ns()
    asbits = ''.join(bytes_to_binary(iter(sourcetext)))
    unpadded = unpadbitstring(asbits)
    indexstream = bigintbitstopairs(unpadded,ascii_symbols)
    decoded = ''.join(decodefromindexes(indexstream,ascii_symbols))
    stoptime = time.time_ns()
    infostring = 'decompression time : ' + str((stoptime - starttime) // 1000000) + 'ms'
    with open(target, 'wb') as f2:
        f2.write(bytes(ord(c) for c in decoded))
    with open(info, 'a') as f3:
        f3.write(infostring)

def test(name):
    s1 = 'original/' + name
    t1 = 'work/ENCODED_' + name
    i1 = 'work/INFO_' + name
    s2 = t1
    t2 = 'work/DECODED_' + name
    i2 = i1
    encode(s1,t1,i1)
    decode(s2,t2,i2)


if __name__ == "__main__":
    if len(sys.argv) == 2: 
        eval(sys.argv[1]) #lazy solution but it works
        
            
