# Instance statistics · profile `smoke`

Boxes after automatic QA. `head` is a mapped auxiliary class (not in the main table).

| group | images | person | helmet | head |
|---|---:|---:|---:|---:|
| val (real) | 300 | 59 | 1168 | 222 |
| seed (real) | 300 | 74 | 1117 | 378 |
| augment | 150 | 50 | 589 | 165 |
| paste | 150 | 189 | 760 | 199 |
| diffusion | 0 | 0 | 0 | 0 |

Newly pasted instances (subset of `paste` boxes): head=54, helmet=64, person=171

Increment share by images: augment 50.0%, paste 50.0%, diffusion 0.0%

## Quota (incremental valid boxes, design §5.3)

| class | have | need | ok |
|---|---:|---:|---|
| person | 239 | 50 | yes |
| helmet | 1349 | 50 | yes |

## Boxes per image

`val (real)`
```
    1 boxes | ####################### 40
    2 boxes | ######################################## 71
    3 boxes | #################### 36
    4 boxes | ##################### 38
    5 boxes | ########### 19
    6 boxes | ############# 23
    7 boxes | ####### 13
    8 boxes | ########## 17
    9 boxes | ###### 11
   10 boxes | ##### 8
   11 boxes | ##### 9
   12 boxes | ## 3
   13 boxes | # 2
   14 boxes | # 2
   16 boxes | # 2
   17 boxes | # 1
   18 boxes | # 1
  20+ boxes | ## 4
```
`seed (real)`
```
    1 boxes | ############################### 52
    2 boxes | ######################################## 67
    3 boxes | ################ 27
    4 boxes | ########################## 44
    5 boxes | ############# 22
    6 boxes | ####### 12
    7 boxes | ########## 16
    8 boxes | ####### 11
    9 boxes | ####### 12
   10 boxes | #### 6
   11 boxes | ##### 9
   12 boxes | ## 3
   13 boxes | # 1
   14 boxes | ## 3
   15 boxes | ## 3
   16 boxes | # 2
   17 boxes | # 1
   18 boxes | # 2
  20+ boxes | #### 7
```
`augment`
```
    1 boxes | ################################## 31
    2 boxes | ######################################## 36
    3 boxes | ############ 11
    4 boxes | #################### 18
    5 boxes | ############# 12
    6 boxes | ###### 5
    7 boxes | ######## 7
    8 boxes | ######## 7
    9 boxes | #### 4
   10 boxes | ### 3
   11 boxes | ### 3
   12 boxes | # 1
   13 boxes | # 1
   14 boxes | ## 2
   15 boxes | ### 3
   17 boxes | # 1
   18 boxes | # 1
  20+ boxes | #### 4
```
`paste`
```
    2 boxes | ######### 6
    3 boxes | ############# 9
    4 boxes | ##################### 15
    5 boxes | ######################################## 28
    6 boxes | ################################## 24
    7 boxes | ##################### 15
    8 boxes | #################### 14
    9 boxes | ########### 8
   10 boxes | ######### 6
   11 boxes | ###### 4
   12 boxes | ####### 5
   13 boxes | #### 3
   14 boxes | #### 3
   15 boxes | ###### 4
   17 boxes | ### 2
   19 boxes | # 1
  20+ boxes | #### 3
```
`diffusion`
```
  (empty)
```
