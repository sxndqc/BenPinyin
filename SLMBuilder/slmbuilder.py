# -*- coding:utf-8 -*-
import json
from multiprocessing import Pool
import time
import config
import logging
import os
import math
import getopt
import sys
import unicodedata
logging.basicConfig(level=logging.INFO)

def getTime(seconds):
    iseconds = int(seconds)
    hour = iseconds / 3600
    minute = (iseconds % 3600) / 60
    second = iseconds % 60
    return (hour, minute, second)

def getVecFromFile(fn, type, sep = ' '):
    f = open(fn, 'r')
    vec = map(type, f.read().split(sep))
    f.close()
    return vec

def getMatFromFile(fn, type, sepr = '\n', sepc = ' '):
    f = open(fn, 'r')
    strVec = f.read().split(sepr)
    mat = [map(type, row.split(sepc)) for row in strVec]
    f.close()
    return mat

def writeVecToFile(vec, fn):
    f = open(fn, 'w')
    f.write(' '.join(map(str, vec)))
    f.close()

def writeMatToFile(mat, fn):
    f = open(fn, 'w')
    strVec = [' '.join(map(str, row)) for row in mat]
    f.write('\n'.join(strVec))
    f.close()

def writeSparseMatToFile(mat, fn, ignore = 0):
    strVec = []
    nrow = len(mat)
    ncol = len(mat[0])
    for rowIdx, row in enumerate(mat):
        for colIdx, item in enumerate(row):
            if item != ignore:
                strVec.append('%d %d %s' % (rowIdx, colIdx, str(item)))
    f = open(fn, 'w')
    f.write('%d %d\n' % (nrow, ncol))
    f.write('\n'.join(strVec))
    f.close()

def getSparseMatFromFile(fn, type, ignore = 0, sepr = '\n', sepc = ' '):
    f = open(fn, 'r')
    strVec = f.read().split(sepr)
    f.close()
    (nrow, ncol) = map(int, strVec[0].split(sepc))
    mat = [[ignore for i in range(ncol)] for i in range(nrow)]
    for info in strVec[1:]:
        infoArr = info.split(sepc)
        (rowIdx, colIdx, value) = (int(infoArr[0]), int(infoArr[1]), type(infoArr[2]))
        mat[rowIdx][colIdx] = value
    return mat

def addToSparseMatFromFile(fn, mat, type, sepr = '\n', sepc = ' '):
    f = open(fn, 'r')
    strVec = f.read().split(sepr)
    f.close()
    for info in strVec[1:]:
        infoArr = info.split(sepc)
        (rowIdx, colIdx, value) = (int(infoArr[0]), int(infoArr[1]), type(infoArr[2]))
        mat[rowIdx][colIdx] += value

def transferToSparseMatFile(fold, fnew, type, ignore = 0):
    mat = getMatFromFile(fold, type)
    writeSparseMatToFile(mat, fnew, ignore)

def getHanziMapping(fn):
    f = file(fn, 'r')
    str = f.read().decode('utf-8')
    f.close()
    hanzi2Idx = {}
    idx2Hanzi = []
    for (idx, hanzi) in enumerate(str):
        hanzi2Idx[hanzi] = idx
        idx2Hanzi.append(hanzi)
    return (hanzi2Idx, idx2Hanzi)

def getTextSet(fn, size = float('inf')):
    f = open(fn, 'r')
    dataset = f.read().decode('utf-8').split('\n')
    f.close()
    textSet = []
    for data in dataset:
        dataObj = json.loads(data)
        textSet.append(dataObj['title'].replace(' ', ''))
        textSet.append(dataObj['html'].replace(' ', ''))
    return textSet[0: min(size, len(textSet))]


def getFreqData(text, freqVec, freqMat, word2Number, number2Word):
    prevWordIdx = None
    prevValid = False
    for idx, word in enumerate(text):
        # if word < config.HANZI_START or word > config.HANZI_END:
        #     prevValid = False
        #     continue
        # try:
        #     wordIdx = word2Number[word]
        # except:
        #     prevValid = False
        #     # logging.info('Exception: %s not in basic Hanzi. Name: %s' % (word, unicodedata.name(word)))
        #     continue
        if not word2Number.has_key(word):
            prevValid = False
            continue
        wordIdx = word2Number[word]
        freqVec[wordIdx] += 1
        if prevValid is True:
            freqMat[prevWordIdx][wordIdx] += 1
            prevWordIdx = wordIdx
            continue
        prevWordIdx = wordIdx
        prevValid = True


def writeFreqFile(fn, hanzi2Idx, idx2Hanzi):
    logging.info('Start processing file: %s ...' % (fn))
    nHanzi = config.N_HANZI
    f = open(fn, 'r')
    text = f.read().decode('utf-8')
    f.close()
    freqVec = [0 for i in range(nHanzi)]
    freqMat = [[0 for i in range(nHanzi)] for i in range(nHanzi)]
    getFreqData(text, freqVec, freqMat, hanzi2Idx, idx2Hanzi)
    writeVecToFile(freqVec, fn + config.VEC_TMP_SUFFIX)
    writeSparseMatToFile(freqMat, fn + config.MAT_TMP_SUFFIX)

def mergeVecData(files):
    freqVec = [0 for i in range(config.N_HANZI)]
    for (idx, file) in enumerate(files):
        logging.info('Merging vec freq file NO.%d ...' % (idx))
        f = open(file, 'r')
        vec = map(int, f.read().split(' '))
        if idx is 0:
            freqVec = [0 for i in range(len(vec))]
        for (wordId, freq) in enumerate(vec):
            freqVec[wordId] += freq
        f.close()
    return freqVec

def mergeMatData(files):
    freqMat = [[0 for i in range(config.N_HANZI)] for i in range(config.N_HANZI)]
    for (idx, file) in enumerate(files):
        logging.info('Merging mat freq file NO.%d ...' % (idx))
        addToSparseMatFromFile(file, freqMat, int)
    return freqMat

def processVec(vec, func = math.log, precision = 4):
    tot = float(sum(vec)) + len(vec)
    newVec = [round(func((item + 1) / tot), precision) for item in vec]
    return newVec

def processMat(mat, func = math.log, precision = 4):
    newMat = []
    for (rowIdx, row) in enumerate(mat):
        newMat.append(processVec(row, func, precision))
    return newMat

def build():
    tstart = time.time()
    logging.info('Getting Hanzi from file ...')
    hanzi2Idx, idx2Hanzi = getHanziMapping(config.HANZI_LIST_FILE)
    files = config.DATA_FILE_BASE

    logging.info('Starting multi-process procedure ...')
    p = Pool(6)
    for file in files:
        p.apply_async(writeFreqFile, args=(file, hanzi2Idx, idx2Hanzi))
    p.close()
    p.join()

    logging.info('Starting merge procedure ...')
    vecFiles = [fn + config.VEC_TMP_SUFFIX for fn in config.DATA_FILE_BASE]
    matFiles = [fn + config.MAT_TMP_SUFFIX for fn in config.DATA_FILE_BASE]
    mergedVec = mergeVecData(vecFiles)
    mergedMat = mergeMatData(matFiles)
    writeVecToFile(mergedVec, config.VEC_FREQ_FILE)
    writeSparseMatToFile(mergedMat, config.MAT_FREQ_FILE)

    logging.info('Starting prob calculation procedure ...')
    processedVec = processVec(mergedVec)
    processedMat = processMat(mergedMat)
    writeVecToFile(processedVec, config.VEC_PROB_FILE)
    writeMatToFile(processedMat, config.MAT_PROB_FILE)

    logging.info('Starting cleaning process ...')
    for file in vecFiles:
        os.remove(file)
    for file in matFiles:
        os.remove(file)

    (hour, minute, second) = getTime(time.time() - tstart)
    logging.info('Build SLM Model all finished in %dh%dmin%ds.' % (hour, minute, second))

def addData(fn):
    tstart = time.time()
    logging.info('Getting Hanzi from file ...')
    hanzi2Idx, idx2Hanzi = getHanziMapping(config.HANZI_LIST_FILE)
    logging.info('Reading language material ...')
    f = open(fn, 'r')
    text = f.read().decode('utf-8')
    f.close()
    logging.info('Getting original vec freq file ...')
    freqVec = getVecFromFile(config.VEC_FREQ_FILE, type = int)
    logging.info('Getting original mat freq file ...')
    freqMat = getSparseMatFromFile(config.MAT_FREQ_FILE, type = int)
    logging.info('Append data from new material ...')
    getFreqData(text, freqVec, freqMat, hanzi2Idx, idx2Hanzi)
    logging.info('Writing new freq files ...')
    writeVecToFile(freqVec, config.VEC_FREQ_FILE)
    writeSparseMatToFile(freqMat, config.MAT_FREQ_FILE)
    logging.info('Starting prob calculation process ...')
    processedVec = processVec(freqVec)
    processedMat = processMat(freqMat)
    logging.info('Writing new prob files ...')
    writeVecToFile(processedVec, config.VEC_PROB_FILE)
    writeMatToFile(processedMat, config.MAT_PROB_FILE)
    (hour, minute, second) = getTime(time.time() - tstart)
    logging.info('Successfully add new data to SLM model, time consumed: %dmin%ds' % (minute, second))

def addFreqData(fn):
    tstart = time.time()
    logging.info('Getting Hanzi from file ...')
    hanzi2Idx, idx2Hanzi = getHanziMapping('WordTable.txt')
    logging.info('Reading language material ...')
    f = open(fn, 'r')
    text = f.read().decode('utf-8')
    f.close()
    logging.info('Getting original vec freq file ...')
    freqVec = getVecFromFile(config.VEC_FREQ_FILE, type = int)
    logging.info('Getting original mat freq file ...')
    freqMat = getSparseMatFromFile(config.MAT_FREQ_FILE, type = int)
    logging.info('Append data from new material ...')
    getFreqData(text, freqVec, freqMat, hanzi2Idx, idx2Hanzi)
    logging.info('Writing new freq files ...')
    writeVecToFile(freqVec, config.VEC_FREQ_FILE)
    writeSparseMatToFile(freqMat, config.MAT_FREQ_FILE)
    (hour, minute, second) = getTime(time.time() - tstart)
    logging.info('Successfully add new freq data to SLM model, time consumed: %dmin%ds' % (minute, second))

def refresh():
    logging.info('Getting original vec freq file ...')
    freqVec = getVecFromFile(config.VEC_FREQ_FILE, type = int)
    logging.info('Getting original mat freq file ...')
    freqMat = getSparseMatFromFile(config.MAT_FREQ_FILE, type = int)
    logging.info('Starting prob calculation process ...')
    processedVec = processVec(freqVec)
    processedMat = processMat(freqMat)
    logging.info('Writing new prob files ...')
    writeVecToFile(processedVec, config.VEC_PROB_FILE)
    writeMatToFile(processedMat, config.MAT_PROB_FILE)
    logging.info('Successfully refresh SLM model.')


def removeFreqData(text, freqVec, freqMat, word2Number, number2Word):
    matChanged = [False for i in range(config.N_HANZI)]
    prevWordIdx = None
    prevValid = False
    for idx, word in enumerate(text):
        if word < config.HANZI_START or word > config.HANZI_END:
            prevValid = False
            continue
        try:
            wordIdx = word2Number[word]
        except:
            prevValid = False
            # logging.info('Exception: %s not in basic Hanzi. Name: %s' % (word, unicodedata.name(word)))
            continue
        freqVec[wordIdx] -= 1
        if prevValid is True:
            freqMat[prevWordIdx][wordIdx] -= 1
            matChanged[prevWordIdx] = True
        prevWordIdx = wordIdx
        prevValid = True
    return matChanged

def removeData(fn):
    tstart = time.time()
    logging.info('Getting Hanzi from file ...')
    hanzi2Idx, idx2Hanzi = getHanziMapping('WordTable.txt')
    logging.info('Reading language material ...')
    f = open(fn, 'r')
    text = f.read().decode('utf-8')
    f.close()
    logging.info('Getting original vec freq file ...')
    freqVec = getVecFromFile(config.VEC_FREQ_FILE, type = int)
    logging.info('Getting original mat freq file ...')
    freqMat = getMatFromFile(config.MAT_FREQ_FILE, type = int)
    logging.info('Append data from new material ...')
    matChanged = removeFreqData(text, freqVec, freqMat, hanzi2Idx, idx2Hanzi)
    logging.info('Detected %d rows changed in mat.' % (matChanged.count(True)))
    logging.info('Writing new freq files ...')
    writeVecToFile(freqVec, config.VEC_FREQ_FILE)
    writeMatToFile(freqMat, config.MAT_FREQ_FILE)
    logging.info('Starting prob calculation process ...')
    processedVec = processVec(freqVec)
    processedMat = freqMat
    for rowIdx, changed in enumerate(matChanged):
        if changed is True:
            processedMat[rowIdx] = processVec(freqMat[rowIdx])
    logging.info('Writing new prob files ...')
    writeVecToFile(processedVec, config.VEC_PROB_FILE)
    writeMatToFile(processedMat, config.MAT_PROB_FILE)
    (hour, minute, second) = getTime(time.time() - tstart)
    logging.info('Successfully add new data to SLM model, time consumed: %dmin%ds' % (minute, second))

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", [])
    except getopt.GetoptError:
        print 'Command not found.'
        sys.exit()

    cmd = args[0]
    if cmd in ['build']:
        build()
        sys.exit()
    elif cmd in ['add']:
        fn = args[1]
        addData(fn)
        sys.exit()
    elif cmd in ['addf']:
        fn = args[1]
        addFreqData(fn)
        sys.exit()
    elif cmd in ['refresh']:
        refresh()
        sys.exit()
    else:
        print 'Command not found.'
        sys.exit()
