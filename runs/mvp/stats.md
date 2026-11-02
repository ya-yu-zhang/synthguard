# Instance statistics · profile `mvp`

Boxes after automatic QA. `head` is a mapped auxiliary class (not in the main table).

| group | images | person | helmet | head |
|---|---:|---:|---:|---:|
| val (real) | 300 | 678 | 622 | 24 |
| seed (real) | 906 | 2139 | 1921 | 105 |
| augment | 453 | 1096 | 996 | 53 |
| paste | 427 | 1206 | 1343 | 337 |
| diffusion | 362 | 820 | 719 | 40 |

Newly pasted instances (subset of `paste` boxes): head=277, helmet=278, person=227

Increment share by images: augment 36.5%, paste 34.4%, diffusion 29.1%

## Quota (incremental valid boxes, design §5.3)

| class | have | need | ok |
|---|---:|---:|---|
| person | 3122 | 500 | yes |
| helmet | 3058 | 500 | yes |

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
    2 boxes | ## 3
    3 boxes | ####################### 43
    4 boxes | ############################### 59
    5 boxes | ######################################## 76
    6 boxes | ################################ 60
    7 boxes | ############################ 54
    8 boxes | ##################### 39
    9 boxes | ################# 33
   10 boxes | ######### 18
   11 boxes | ###### 11
   12 boxes | #### 8
   13 boxes | ### 5
   14 boxes | #### 7
   15 boxes | # 1
   16 boxes | ## 3
   19 boxes | # 1
  20+ boxes | ### 6
```
`diffusion`
```
    1 boxes | ## 7
    2 boxes | ######################################## 145
    3 boxes | # 5
    4 boxes | ######################### 92
    5 boxes | #### 13
    6 boxes | ############## 49
    7 boxes | # 4
    8 boxes | ##### 17
    9 boxes | ## 7
   10 boxes | ## 8
   11 boxes | # 1
   12 boxes | # 5
   13 boxes | # 1
   14 boxes | # 2
   16 boxes | # 1
   19 boxes | # 1
  20+ boxes | # 4
```
