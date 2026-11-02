# Instance statistics · profile `mvp`

Boxes after automatic QA. `head` is a mapped auxiliary class (not in the main table).

| group | images | person | helmet | head |
|---|---:|---:|---:|---:|
| val (real) | 300 | 678 | 622 | 24 |
| seed (real) | 906 | 2139 | 1921 | 105 |
| augment | 453 | 1096 | 996 | 53 |
| paste | 421 | 1137 | 1289 | 323 |
| diffusion | 0 | 0 | 0 | 0 |

Newly pasted instances (subset of `paste` boxes): head=271, helmet=300, person=170

Increment share by images: augment 51.8%, paste 48.2%, diffusion 0.0%

## Quota (incremental valid boxes, design §5.3)

| class | have | need | ok |
|---|---:|---:|---|
| person | 2233 | 500 | yes |
| helmet | 2285 | 500 | yes |

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
    1 boxes | ## 14
    2 boxes | ######################################## 346
    3 boxes | ### 25
    4 boxes | ######################### 219
    5 boxes | #### 34
    6 boxes | ############## 117
    7 boxes | ## 14
    8 boxes | ###### 49
    9 boxes | ## 13
   10 boxes | ### 30
   11 boxes | # 5
   12 boxes | # 9
   13 boxes | # 4
   14 boxes | # 7
   15 boxes | # 4
   16 boxes | # 3
   19 boxes | # 2
  20+ boxes | # 11
```
`augment`
```
    1 boxes | # 4
    2 boxes | ######################################## 173
    3 boxes | ### 13
    4 boxes | ######################### 106
    5 boxes | ### 15
    6 boxes | ############### 65
    7 boxes | # 5
    8 boxes | #### 19
    9 boxes | ## 8
   10 boxes | #### 19
   11 boxes | # 3
   12 boxes | # 5
   13 boxes | # 4
   14 boxes | # 1
   15 boxes | # 3
   16 boxes | # 3
   19 boxes | # 1
  20+ boxes | # 6
```
`paste`
```
    2 boxes | # 2
    3 boxes | ########################## 53
    4 boxes | ########################### 56
    5 boxes | ######################################## 83
    6 boxes | ############################ 59
    7 boxes | ############################ 58
    8 boxes | ############## 30
    9 boxes | ############# 28
   10 boxes | ###### 13
   11 boxes | #### 8
   12 boxes | #### 9
   13 boxes | ### 6
   14 boxes | ## 4
   15 boxes | # 2
   16 boxes | # 3
   19 boxes | # 1
  20+ boxes | ### 6
```
`diffusion`
```
  (empty)
```
