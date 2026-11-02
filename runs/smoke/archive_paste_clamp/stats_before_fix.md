# Instance statistics · profile `smoke`

Boxes after automatic QA. `head` is a mapped auxiliary class (not in the main table).

| group | images | person | helmet | head |
|---|---:|---:|---:|---:|
| val (real) | 300 | 678 | 622 | 24 |
| seed (real) | 300 | 758 | 647 | 33 |
| augment | 150 | 329 | 270 | 21 |
| paste | 136 | 415 | 452 | 114 |
| diffusion | 0 | 0 | 0 | 0 |

Newly pasted instances (subset of `paste` boxes): head=94, helmet=90, person=64

Increment share by images: augment 52.4%, paste 47.6%, diffusion 0.0%

## Quota (incremental valid boxes, design §5.3)

| class | have | need | ok |
|---|---:|---:|---|
| person | 744 | 50 | yes |
| helmet | 722 | 50 | yes |

## Boxes per image

`val (real)`
```
    1 boxes | ## 6
    2 boxes | ######################################## 121
    3 boxes | ## 7
    4 boxes | ######################### 76
    5 boxes | ## 6
    6 boxes | ############ 37
    7 boxes | # 3
    8 boxes | ##### 14
    9 boxes | ## 6
   10 boxes | ## 6
   11 boxes | # 2
   12 boxes | ## 5
   13 boxes | # 2
   14 boxes | # 3
   15 boxes | # 1
   16 boxes | # 1
   17 boxes | # 1
   18 boxes | # 3
```
`seed (real)`
```
    1 boxes | ## 5
    2 boxes | ######################################## 112
    3 boxes | ### 9
    4 boxes | ########################## 73
    5 boxes | #### 10
    6 boxes | ############## 40
    7 boxes | ## 6
    8 boxes | #### 12
    9 boxes | # 3
   10 boxes | ### 9
   11 boxes | # 3
   12 boxes | # 3
   13 boxes | # 1
   14 boxes | # 3
   15 boxes | # 3
   16 boxes | # 2
  20+ boxes | ## 6
```
`augment`
```
    1 boxes | # 2
    2 boxes | ######################################## 65
    3 boxes | ## 3
    4 boxes | ##################### 34
    5 boxes | #### 7
    6 boxes | ############## 22
    7 boxes | # 2
    8 boxes | #### 6
    9 boxes | # 1
   10 boxes | # 2
   12 boxes | # 2
   14 boxes | # 1
   15 boxes | # 1
   16 boxes | # 2
```
`paste`
```
    3 boxes | ########################### 16
    4 boxes | ######################### 15
    5 boxes | ######################################## 24
    6 boxes | ##################################### 22
    7 boxes | ############################ 17
    8 boxes | ###################### 13
    9 boxes | ############ 7
   10 boxes | ########## 6
   11 boxes | ## 1
   12 boxes | ### 2
   13 boxes | ##### 3
   14 boxes | ## 1
   15 boxes | ##### 3
   16 boxes | ## 1
   18 boxes | ## 1
  20+ boxes | ####### 4
```
`diffusion`
```
  (empty)
```
