# Instance statistics · profile `mvp`

Boxes after automatic QA. `head` is a mapped auxiliary class (not in the main table).

| group | images | person | helmet | head |
|---|---:|---:|---:|---:|
| val (real) | 1000 | 124 | 3846 | 999 |
| seed (real) | 1000 | 199 | 3680 | 1318 |
| augment | 500 | 75 | 1825 | 623 |
| paste | 495 | 707 | 2470 | 737 |
| diffusion | 0 | 0 | 0 | 0 |

Newly pasted instances (subset of `paste` boxes): head=164, helmet=181, person=598

Increment share by images: augment 50.3%, paste 49.7%, diffusion 0.0%

## Quota (incremental valid boxes, design §5.3)

| class | have | need | ok |
|---|---:|---:|---|
| person | 782 | 500 | yes |
| helmet | 4295 | 500 | yes |

## Boxes per image

`val (real)`
```
    1 boxes | ######################### 140
    2 boxes | ######################################## 224
    3 boxes | ###################### 124
    4 boxes | ####################### 130
    5 boxes | ########### 62
    6 boxes | ############ 65
    7 boxes | ######## 47
    8 boxes | ######## 43
    9 boxes | ###### 36
   10 boxes | ###### 32
   11 boxes | #### 22
   12 boxes | ### 18
   13 boxes | ## 11
   14 boxes | # 7
   15 boxes | # 7
   16 boxes | # 8
   17 boxes | # 6
   18 boxes | # 4
  20+ boxes | ## 14
```
`seed (real)`
```
    1 boxes | ########################## 143
    2 boxes | ######################################## 217
    3 boxes | ################## 97
    4 boxes | ######################## 128
    5 boxes | ############## 77
    6 boxes | ############# 71
    7 boxes | ######## 46
    8 boxes | ########## 54
    9 boxes | ####### 37
   10 boxes | ###### 32
   11 boxes | #### 19
   12 boxes | ### 16
   13 boxes | # 8
   14 boxes | ## 9
   15 boxes | ## 10
   16 boxes | # 8
   17 boxes | # 4
   18 boxes | # 5
   19 boxes | # 2
  20+ boxes | ### 17
```
`augment`
```
    0 boxes | # 1
    1 boxes | ############################## 80
    2 boxes | ######################################## 105
    3 boxes | ################## 47
    4 boxes | ###################### 58
    5 boxes | ############## 36
    6 boxes | ############# 34
    7 boxes | ########### 29
    8 boxes | ######### 24
    9 boxes | ########## 25
   10 boxes | ##### 12
   11 boxes | #### 10
   12 boxes | ### 7
   13 boxes | ## 4
   14 boxes | ### 8
   15 boxes | ### 8
   16 boxes | # 2
   18 boxes | # 3
   19 boxes | # 2
  20+ boxes | ## 5
```
`paste`
```
    2 boxes | ########## 16
    3 boxes | ##################### 34
    4 boxes | ################################ 52
    5 boxes | ######################################## 66
    6 boxes | ##################################### 61
    7 boxes | ################################### 58
    8 boxes | ##################### 34
    9 boxes | #################### 33
   10 boxes | ######################## 40
   11 boxes | ################ 26
   12 boxes | ########## 16
   13 boxes | ######## 14
   14 boxes | ####### 11
   15 boxes | #### 6
   16 boxes | #### 6
   17 boxes | #### 6
   18 boxes | # 1
   19 boxes | ## 4
  20+ boxes | ####### 11
```
`diffusion`
```
  (empty)
```
